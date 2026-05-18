use super::*;
use chrono::TimeZone;

fn fonte(nome: &str, tags: &[&str]) -> Fonte {
    Fonte {
        nome: nome.to_string(),
        tags: tags.iter().map(|s| s.to_string()).collect(),
        url: format!("https://example.com/{}", nome),
    }
}

// ---------- filter_by_tags ----------

#[test]
fn filter_by_tags_empty_returns_all() {
    let fs = vec![fonte("a", &["IA"]), fonte("b", &["Rust"])];
    let out = filter_by_tags(fs.clone(), &[], false);
    assert_eq!(out.len(), 2);
}

#[test]
fn filter_by_tags_or_match() {
    let fs = vec![
        fonte("a", &["IA"]),
        fonte("b", &["Rust"]),
        fonte("c", &["Go"]),
    ];
    let out = filter_by_tags(fs, &["IA".into(), "Rust".into()], false);
    let nomes: Vec<_> = out.iter().map(|f| f.nome.as_str()).collect();
    assert_eq!(nomes, vec!["a", "b"]);
}

#[test]
fn filter_by_tags_and_match() {
    let fs = vec![
        fonte("a", &["IA", "LLM"]),
        fonte("b", &["IA"]),
        fonte("c", &["LLM"]),
    ];
    let out = filter_by_tags(fs, &["IA".into(), "LLM".into()], true);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].nome, "a");
}

#[test]
fn filter_by_tags_case_insensitive() {
    let fs = vec![fonte("a", &["IA"])];
    let out = filter_by_tags(fs, &["ia".into()], false);
    assert_eq!(out.len(), 1);
}

#[test]
fn filter_by_tags_no_match_returns_empty() {
    let fs = vec![fonte("a", &["IA"])];
    let out = filter_by_tags(fs, &["Cobol".into()], false);
    assert!(out.is_empty());
}

// ---------- Fonte deserialization ----------

#[test]
fn fonte_deserializes_from_real_schema() {
    let json = r#"[
        {"nome":"arXiv AI","tags":["Papers","IA"],"url":"http://example.com/a"},
        {"nome":"HN","tags":["Tech"],"url":"http://example.com/b"}
    ]"#;
    let fontes: Vec<Fonte> = serde_json::from_str(json).unwrap();
    assert_eq!(fontes.len(), 2);
    assert_eq!(fontes[0].nome, "arXiv AI");
    assert_eq!(fontes[0].tags, vec!["Papers", "IA"]);
}

#[test]
fn fonte_missing_field_fails() {
    let json = r#"[{"nome":"x","url":"http://a"}]"#; // tags faltando
    let r: serde_json::Result<Vec<Fonte>> = serde_json::from_str(json);
    assert!(r.is_err());
}

#[test]
fn load_fontes_reads_file() {
    let dir = std::env::temp_dir().join("leitor_links_test_load");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("fontes.json");
    std::fs::write(
        &path,
        r#"[{"nome":"x","tags":["t"],"url":"http://example.com"}]"#,
    )
    .unwrap();
    let fs = load_fontes(&path).unwrap();
    assert_eq!(fs.len(), 1);
    assert_eq!(fs[0].nome, "x");
}

// ---------- filter_and_sort_entries ----------

fn make_entry(id: &str, published: Option<DateTime<Utc>>) -> feed_rs::model::Entry {
    let mut e = feed_rs::model::Entry::default();
    e.id = id.to_string();
    e.published = published;
    e
}

#[test]
fn filter_sort_keeps_recent_drops_old() {
    let now = Utc::now();
    let cutoff = now - Duration::days(3);
    let entries = vec![
        make_entry("recent", Some(now - Duration::days(1))),
        make_entry("old", Some(now - Duration::days(10))),
    ];
    let out = filter_and_sort_entries(entries, cutoff, 10);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].id, "recent");
}

#[test]
fn filter_sort_keeps_entries_without_date() {
    let cutoff = Utc::now() - Duration::days(3);
    let entries = vec![make_entry("no-date", None)];
    let out = filter_and_sort_entries(entries, cutoff, 10);
    assert_eq!(out.len(), 1);
}

#[test]
fn filter_sort_orders_newest_first() {
    let now = Utc::now();
    let cutoff = now - Duration::days(30);
    let entries = vec![
        make_entry("older", Some(now - Duration::days(5))),
        make_entry("newest", Some(now - Duration::hours(1))),
        make_entry("middle", Some(now - Duration::days(2))),
    ];
    let out = filter_and_sort_entries(entries, cutoff, 10);
    let ids: Vec<_> = out.iter().map(|e| e.id.as_str()).collect();
    assert_eq!(ids, vec!["newest", "middle", "older"]);
}

#[test]
fn filter_sort_truncates_to_max_items() {
    let now = Utc::now();
    let cutoff = now - Duration::days(30);
    let entries: Vec<_> = (0..10)
        .map(|i| make_entry(&format!("e{i}"), Some(now - Duration::hours(i))))
        .collect();
    let out = filter_and_sort_entries(entries, cutoff, 3);
    assert_eq!(out.len(), 3);
}

#[test]
fn filter_sort_falls_back_to_updated_when_published_missing() {
    let now = Utc::now();
    let cutoff = now - Duration::days(3);
    let mut e = feed_rs::model::Entry::default();
    e.id = "x".to_string();
    e.updated = Some(now - Duration::days(1));
    let out = filter_and_sort_entries(vec![e], cutoff, 10);
    assert_eq!(out.len(), 1);
}

// ---------- feed parsing (RSS sample) ----------

#[test]
fn parses_rss_2_0_feed() {
    let rss = r#"<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Sample</title>
        <link>http://example.com</link>
        <description>x</description>
        <item>
          <title>Post 1</title>
          <link>http://example.com/1</link>
          <pubDate>Mon, 01 Jan 2026 12:00:00 GMT</pubDate>
          <description>desc 1</description>
        </item>
      </channel>
    </rss>"#;
    let feed = feed_rs::parser::parse(rss.as_bytes()).unwrap();
    assert_eq!(feed.entries.len(), 1);
    assert_eq!(feed.entries[0].title.as_ref().unwrap().content, "Post 1");
}

#[test]
fn parses_atom_feed() {
    let atom = r#"<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Sample</title>
      <id>urn:test</id>
      <updated>2026-01-01T00:00:00Z</updated>
      <entry>
        <title>Atom Post</title>
        <id>urn:a</id>
        <updated>2026-01-01T00:00:00Z</updated>
        <link href="http://example.com/a"/>
      </entry>
    </feed>"#;
    let feed = feed_rs::parser::parse(atom.as_bytes()).unwrap();
    assert_eq!(feed.entries.len(), 1);
}

#[test]
fn parse_then_filter_pipeline_end_to_end() {
    // RSS com 2 itens (1 recente, 1 antigo) → após filtro deve sobrar 1
    let recent = (Utc::now() - Duration::days(1))
        .format("%a, %d %b %Y %H:%M:%S GMT")
        .to_string();
    let rss = format!(
        r#"<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <title>t</title><link>http://e</link><description>d</description>
          <item><title>recent</title><link>http://e/1</link><pubDate>{}</pubDate></item>
          <item><title>old</title><link>http://e/2</link><pubDate>Mon, 01 Jan 2020 00:00:00 GMT</pubDate></item>
        </channel></rss>"#,
        recent
    );
    let feed = feed_rs::parser::parse(rss.as_bytes()).unwrap();
    let cutoff = Utc::now() - Duration::days(3);
    let out = filter_and_sort_entries(feed.entries, cutoff, 10);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].title.as_ref().unwrap().content, "recent");
}

// ---------- slug (filename) ----------

#[test]
fn slug_handles_spaces_and_accents() {
    assert_eq!(
        slug::slugify("arXiv Artificial Intelligence"),
        "arxiv-artificial-intelligence"
    );
    assert_eq!(slug::slugify("Hacker News (Top 50)"), "hacker-news-top-50");
    assert_eq!(slug::slugify("Café com Código"), "cafe-com-codigo");
}

// ---------- guard: confirma valor concreto de DateTime ----------

#[test]
fn datetime_serialization_is_rfc3339() {
    let dt: DateTime<Utc> = Utc.with_ymd_and_hms(2026, 5, 18, 14, 0, 0).unwrap();
    let s = serde_json::to_string(&dt).unwrap();
    assert_eq!(s, "\"2026-05-18T14:00:00Z\"");
}
