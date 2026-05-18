use anyhow::{Context, Result};
use chrono::{DateTime, Duration, Utc};
use clap::{Parser, Subcommand};
use feed_rs::parser;
use futures::stream::{self, StreamExt};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::Duration as StdDuration;

#[derive(Parser, Debug)]
#[command(name = "leitor_links", about = "Lê feeds RSS/Atom e salva itens recentes em JSON")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Busca itens recentes de todas (ou algumas) fontes
    Fetch {
        /// Caminho do JSON de fontes
        #[arg(short, long, default_value = "../links_fontes.json")]
        input: PathBuf,

        /// Pasta de saída (uma subpasta YYYY-MM-DD será criada dentro)
        #[arg(short, long, default_value = "./output")]
        output: PathBuf,

        /// Tags para filtrar (separadas por vírgula). Vazio = todas as fontes
        #[arg(short, long, value_delimiter = ',')]
        tags: Vec<String>,

        /// Exigir TODAS as tags (AND). Default é OR
        #[arg(long)]
        match_all: bool,

        /// Pegar apenas itens publicados nos últimos N dias
        #[arg(long, default_value_t = 3)]
        since_days: i64,

        /// Máximo de itens por fonte
        #[arg(long, default_value_t = 20)]
        max_items: usize,

        /// Número de fontes processadas em paralelo
        #[arg(long, default_value_t = 5)]
        concurrency: usize,

        /// Desabilita scraping da página completa (usa só o conteúdo do feed)
        #[arg(long)]
        no_full_content: bool,
    },

    /// Lista as tags disponíveis no JSON de fontes
    ListTags {
        #[arg(short, long, default_value = "../links_fontes.json")]
        input: PathBuf,
    },

    /// Lista as fontes no JSON
    ListSources {
        #[arg(short, long, default_value = "../links_fontes.json")]
        input: PathBuf,
    },
}

#[derive(Debug, Deserialize, Clone)]
struct Fonte {
    nome: String,
    tags: Vec<String>,
    url: String,
}

#[derive(Debug, Serialize)]
struct Item {
    title: Option<String>,
    link: Option<String>,
    published: Option<DateTime<Utc>>,
    summary: Option<String>,
    /// Conteúdo do feed (se houver)
    feed_content: Option<String>,
    /// Texto extraído da página completa (scraping)
    full_text: Option<String>,
    /// Erro de scraping, se houver
    scrape_error: Option<String>,
}

#[derive(Debug, Serialize)]
struct FonteOutput {
    fonte: String,
    tags: Vec<String>,
    url: String,
    fetched_at: DateTime<Utc>,
    item_count: usize,
    items: Vec<Item>,
}

fn load_fontes(path: &Path) -> Result<Vec<Fonte>> {
    let content = std::fs::read_to_string(path)
        .with_context(|| format!("falha ao ler {}", path.display()))?;
    let fontes: Vec<Fonte> = serde_json::from_str(&content)
        .with_context(|| format!("falha ao parsear JSON de {}", path.display()))?;
    Ok(fontes)
}

fn filter_by_tags(fontes: Vec<Fonte>, tags: &[String], match_all: bool) -> Vec<Fonte> {
    if tags.is_empty() {
        return fontes;
    }
    let wanted: Vec<String> = tags.iter().map(|t| t.to_lowercase()).collect();
    fontes
        .into_iter()
        .filter(|f| {
            let lower: Vec<String> = f.tags.iter().map(|t| t.to_lowercase()).collect();
            if match_all {
                wanted.iter().all(|w| lower.contains(w))
            } else {
                wanted.iter().any(|w| lower.contains(w))
            }
        })
        .collect()
}

fn filter_and_sort_entries(
    entries: Vec<feed_rs::model::Entry>,
    cutoff: DateTime<Utc>,
    max_items: usize,
) -> Vec<feed_rs::model::Entry> {
    let mut filtered: Vec<feed_rs::model::Entry> = entries
        .into_iter()
        .filter(|e| {
            e.published
                .or(e.updated)
                .map(|d| d >= cutoff)
                .unwrap_or(true) // sem data → mantém
        })
        .collect();

    filtered.sort_by(|a, b| {
        let da = a.published.or(a.updated).unwrap_or_else(Utc::now);
        let db = b.published.or(b.updated).unwrap_or_else(Utc::now);
        db.cmp(&da)
    });
    filtered.truncate(max_items);
    filtered
}

async fn scrape_full_text(client: &reqwest::Client, url: &str) -> Result<String> {
    let resp = client.get(url).send().await?.error_for_status()?;
    let html = resp.text().await?;
    let parsed_url = url::Url::parse(url)?;
    let mut cursor = std::io::Cursor::new(html.into_bytes());
    let product = readability::extractor::extract(&mut cursor, &parsed_url)
        .map_err(|e| anyhow::anyhow!("readability: {e:?}"))?;
    Ok(product.text)
}

async fn process_fonte(
    client: reqwest::Client,
    fonte: Fonte,
    since_days: i64,
    max_items: usize,
    full_content: bool,
) -> Result<FonteOutput> {
    let resp = client
        .get(&fonte.url)
        .send()
        .await
        .with_context(|| format!("GET {}", fonte.url))?
        .error_for_status()
        .with_context(|| format!("status != 2xx em {}", fonte.url))?;

    let bytes = resp.bytes().await?;
    let feed = parser::parse(&bytes[..])
        .with_context(|| format!("falha ao parsear feed {}", fonte.url))?;

    let cutoff = Utc::now() - Duration::days(since_days);
    let items_filtrados = filter_and_sort_entries(feed.entries, cutoff, max_items);

    let mut items_out = Vec::with_capacity(items_filtrados.len());
    for entry in items_filtrados {
        let link = entry.links.first().map(|l| l.href.clone());
        let feed_content = entry
            .content
            .as_ref()
            .and_then(|c| c.body.clone())
            .or_else(|| entry.summary.as_ref().map(|s| s.content.clone()));

        let (full_text, scrape_error) = if full_content {
            if let Some(ref url) = link {
                match scrape_full_text(&client, url).await {
                    Ok(t) => (Some(t), None),
                    Err(e) => (None, Some(format!("{e:#}"))),
                }
            } else {
                (None, Some("sem link para scrape".to_string()))
            }
        } else {
            (None, None)
        };

        items_out.push(Item {
            title: entry.title.map(|t| t.content),
            link,
            published: entry.published.or(entry.updated),
            summary: entry.summary.map(|s| s.content),
            feed_content,
            full_text,
            scrape_error,
        });
    }

    Ok(FonteOutput {
        fonte: fonte.nome,
        tags: fonte.tags,
        url: fonte.url,
        fetched_at: Utc::now(),
        item_count: items_out.len(),
        items: items_out,
    })
}

async fn cmd_fetch(
    input: PathBuf,
    output: PathBuf,
    tags: Vec<String>,
    match_all: bool,
    since_days: i64,
    max_items: usize,
    concurrency: usize,
    full_content: bool,
) -> Result<()> {
    let fontes = load_fontes(&input)?;
    let total_inicial = fontes.len();
    let fontes = filter_by_tags(fontes, &tags, match_all);

    if fontes.is_empty() {
        anyhow::bail!("nenhuma fonte casa com as tags fornecidas");
    }

    println!(
        "→ {} fontes selecionadas (de {} no arquivo), since_days={}, max_items={}, full_content={}",
        fontes.len(),
        total_inicial,
        since_days,
        max_items,
        full_content
    );

    let today = Utc::now().format("%Y-%m-%d").to_string();
    let out_dir = output.join(&today);
    std::fs::create_dir_all(&out_dir)
        .with_context(|| format!("criando {}", out_dir.display()))?;

    let client = reqwest::Client::builder()
        .user_agent("leitor_links/0.1 (+https://carta.com)")
        .timeout(StdDuration::from_secs(30))
        .build()?;

    let results: Vec<(String, Result<FonteOutput>)> = stream::iter(fontes.into_iter())
        .map(|f| {
            let client = client.clone();
            let nome = f.nome.clone();
            async move {
                let r = process_fonte(client, f, since_days, max_items, full_content).await;
                (nome, r)
            }
        })
        .buffer_unordered(concurrency)
        .collect()
        .await;

    let mut ok = 0;
    let mut fail = 0;
    let mut total_items = 0;
    for (nome, res) in results {
        match res {
            Ok(out) => {
                let slug = slug::slugify(&out.fonte);
                let path = out_dir.join(format!("{slug}.json"));
                let json = serde_json::to_string_pretty(&out)?;
                std::fs::write(&path, json)
                    .with_context(|| format!("escrevendo {}", path.display()))?;
                println!("  ✓ {} — {} itens → {}", nome, out.item_count, path.display());
                ok += 1;
                total_items += out.item_count;
            }
            Err(e) => {
                eprintln!("  ✗ {nome} — {e:#}");
                fail += 1;
            }
        }
    }

    println!(
        "\nResumo: {ok} OK, {fail} FAIL, {total_items} itens salvos em {}",
        out_dir.display()
    );

    if ok == 0 {
        anyhow::bail!("todas as fontes falharam");
    }
    Ok(())
}

fn cmd_list_tags(input: PathBuf) -> Result<()> {
    let fontes = load_fontes(&input)?;
    let mut tags: Vec<String> = fontes.into_iter().flat_map(|f| f.tags).collect();
    tags.sort();
    tags.dedup();
    for t in tags {
        println!("{t}");
    }
    Ok(())
}

fn cmd_list_sources(input: PathBuf) -> Result<()> {
    let fontes = load_fontes(&input)?;
    for f in fontes {
        println!("{} [{}] — {}", f.nome, f.tags.join(", "), f.url);
    }
    Ok(())
}

#[cfg(test)]
mod tests;

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Fetch {
            input,
            output,
            tags,
            match_all,
            since_days,
            max_items,
            concurrency,
            no_full_content,
        } => {
            cmd_fetch(
                input,
                output,
                tags,
                match_all,
                since_days,
                max_items,
                concurrency,
                !no_full_content,
            )
            .await
        }
        Command::ListTags { input } => cmd_list_tags(input),
        Command::ListSources { input } => cmd_list_sources(input),
    }
}
