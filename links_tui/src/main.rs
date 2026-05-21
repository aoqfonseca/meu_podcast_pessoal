use std::{
    fs,
    io::{self, Stdout},
    path::PathBuf,
};

use anyhow::{Context, Result};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode},
};
use ratatui::{
    Terminal,
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph, Wrap},
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct Link {
    nome: String,
    tags: Vec<String>,
    url: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Mode {
    List,
    Editing,
    ConfirmDelete,
    ConfirmQuit,
    Help,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Field {
    Nome,
    Tags,
    Url,
}

impl Field {
    fn next(self) -> Self {
        match self {
            Field::Nome => Field::Tags,
            Field::Tags => Field::Url,
            Field::Url => Field::Nome,
        }
    }
    fn prev(self) -> Self {
        match self {
            Field::Nome => Field::Url,
            Field::Tags => Field::Nome,
            Field::Url => Field::Tags,
        }
    }
}

struct EditBuf {
    nome: String,
    tags: String,
    url: String,
    field: Field,
    editing_index: Option<usize>,
}

struct App {
    path: PathBuf,
    links: Vec<Link>,
    state: ListState,
    mode: Mode,
    edit: Option<EditBuf>,
    status: String,
    dirty: bool,
}

impl App {
    fn load(path: PathBuf) -> Result<Self> {
        let links: Vec<Link> = if path.exists() {
            let raw = fs::read_to_string(&path)
                .with_context(|| format!("reading {}", path.display()))?;
            serde_json::from_str(&raw).with_context(|| "parsing JSON")?
        } else {
            Vec::new()
        };
        let mut state = ListState::default();
        if !links.is_empty() {
            state.select(Some(0));
        }
        Ok(App {
            path,
            links,
            state,
            mode: Mode::List,
            edit: None,
            status: "Press '?' for help | 'a' add | 'e' edit | 'd' delete | 's' save | 'q' quit".into(),
            dirty: false,
        })
    }

    fn save(&mut self) -> Result<()> {
        let json = serde_json::to_string_pretty(&self.links)?;
        fs::write(&self.path, json + "\n")?;
        self.dirty = false;
        self.status = format!("Saved {} links to {}", self.links.len(), self.path.display());
        Ok(())
    }

    fn select_next(&mut self) {
        if self.links.is_empty() {
            return;
        }
        let i = self.state.selected().map(|i| (i + 1) % self.links.len()).unwrap_or(0);
        self.state.select(Some(i));
    }
    fn select_prev(&mut self) {
        if self.links.is_empty() {
            return;
        }
        let len = self.links.len();
        let i = self.state.selected().map(|i| (i + len - 1) % len).unwrap_or(0);
        self.state.select(Some(i));
    }

    fn start_add(&mut self) {
        self.edit = Some(EditBuf {
            nome: String::new(),
            tags: String::new(),
            url: String::new(),
            field: Field::Nome,
            editing_index: None,
        });
        self.mode = Mode::Editing;
        self.status = "Editing (new). Tab: next field | Shift+Tab: prev | Enter: save | Esc: cancel".into();
    }

    fn start_edit(&mut self) {
        let Some(i) = self.state.selected() else { return };
        let Some(link) = self.links.get(i) else { return };
        self.edit = Some(EditBuf {
            nome: link.nome.clone(),
            tags: link.tags.join(", "),
            url: link.url.clone(),
            field: Field::Nome,
            editing_index: Some(i),
        });
        self.mode = Mode::Editing;
        self.status = "Editing. Tab: next field | Shift+Tab: prev | Enter: save | Esc: cancel".into();
    }

    fn commit_edit(&mut self) {
        let Some(buf) = self.edit.take() else { return };
        let tags: Vec<String> = buf
            .tags
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();
        let link = Link {
            nome: buf.nome.trim().to_string(),
            tags,
            url: buf.url.trim().to_string(),
        };
        if link.nome.is_empty() || link.url.is_empty() {
            self.status = "Nome and URL are required. Press 'e' or 'a' to retry.".into();
            self.mode = Mode::List;
            return;
        }
        match buf.editing_index {
            Some(i) if i < self.links.len() => {
                self.links[i] = link;
                self.status = format!("Updated row {}. Press 's' to save to disk.", i + 1);
            }
            _ => {
                self.links.push(link);
                self.state.select(Some(self.links.len() - 1));
                self.status = "Added. Press 's' to save to disk.".into();
            }
        }
        self.dirty = true;
        self.mode = Mode::List;
    }

    fn cancel_edit(&mut self) {
        self.edit = None;
        self.mode = Mode::List;
        self.status = "Edit cancelled.".into();
    }

    fn delete_selected(&mut self) {
        let Some(i) = self.state.selected() else { return };
        if i >= self.links.len() {
            return;
        }
        let removed = self.links.remove(i);
        if self.links.is_empty() {
            self.state.select(None);
        } else if i >= self.links.len() {
            self.state.select(Some(self.links.len() - 1));
        }
        self.dirty = true;
        self.status = format!("Deleted '{}'. Press 's' to save.", removed.nome);
    }
}

fn main() -> Result<()> {
    let path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(default_links_path);

    let mut app = App::load(path)?;
    let mut terminal = setup_terminal()?;
    let res = run(&mut terminal, &mut app);
    restore_terminal(&mut terminal)?;
    res
}

fn default_links_path() -> PathBuf {
    // Default: ../links_fontes.json relative to this crate
    let mut p = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    p.push("../links_fontes.json");
    p
}

fn setup_terminal() -> Result<Terminal<CrosstermBackend<Stdout>>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    Ok(Terminal::new(backend)?)
}

fn restore_terminal(terminal: &mut Terminal<CrosstermBackend<Stdout>>) -> Result<()> {
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;
    Ok(())
}

fn run(terminal: &mut Terminal<CrosstermBackend<Stdout>>, app: &mut App) -> Result<()> {
    loop {
        terminal.draw(|f| ui(f, app))?;
        if !event::poll(std::time::Duration::from_millis(250))? {
            continue;
        }
        let Event::Key(key) = event::read()? else { continue };
        if key.kind != KeyEventKind::Press {
            continue;
        }
        match app.mode {
            Mode::List => match key.code {
                KeyCode::Char('q') => {
                    if app.dirty {
                        app.mode = Mode::ConfirmQuit;
                        app.status = "Unsaved changes. Quit anyway? (y/n)".into();
                    } else {
                        return Ok(());
                    }
                }
                KeyCode::Char('s') => match app.save() {
                    Ok(()) => {}
                    Err(e) => app.status = format!("Save failed: {e}"),
                },
                KeyCode::Char('a') => app.start_add(),
                KeyCode::Char('e') => app.start_edit(),
                KeyCode::Char('d') => {
                    if app.state.selected().is_some() {
                        app.mode = Mode::ConfirmDelete;
                        app.status = "Delete selected link? (y/n)".into();
                    }
                }
                KeyCode::Down | KeyCode::Char('j') => app.select_next(),
                KeyCode::Up | KeyCode::Char('k') => app.select_prev(),
                KeyCode::Char('?') => {
                    app.mode = Mode::Help;
                    app.status = "Help — press Esc or '?' to close".into();
                }
                _ => {}
            },
            Mode::Help => match key.code {
                KeyCode::Esc | KeyCode::Char('?') | KeyCode::Char('q') => {
                    app.mode = Mode::List;
                    app.status = "Press '?' for help".into();
                }
                _ => {}
            },
            Mode::Editing => handle_edit_key(app, key.code),
            Mode::ConfirmDelete => match key.code {
                KeyCode::Char('y') | KeyCode::Char('Y') => {
                    app.delete_selected();
                    app.mode = Mode::List;
                }
                _ => {
                    app.mode = Mode::List;
                    app.status = "Delete cancelled.".into();
                }
            },
            Mode::ConfirmQuit => match key.code {
                KeyCode::Char('y') | KeyCode::Char('Y') => return Ok(()),
                _ => {
                    app.mode = Mode::List;
                    app.status = "Continuing. Press 's' to save.".into();
                }
            },
        }
    }
}

fn handle_edit_key(app: &mut App, code: KeyCode) {
    let Some(buf) = app.edit.as_mut() else { return };
    match code {
        KeyCode::Esc => app.cancel_edit(),
        KeyCode::Enter => app.commit_edit(),
        KeyCode::Tab => buf.field = buf.field.next(),
        KeyCode::BackTab => buf.field = buf.field.prev(),
        KeyCode::Backspace => {
            let target = match buf.field {
                Field::Nome => &mut buf.nome,
                Field::Tags => &mut buf.tags,
                Field::Url => &mut buf.url,
            };
            target.pop();
        }
        KeyCode::Char(c) => {
            let target = match buf.field {
                Field::Nome => &mut buf.nome,
                Field::Tags => &mut buf.tags,
                Field::Url => &mut buf.url,
            };
            target.push(c);
        }
        _ => {}
    }
}

fn ui(f: &mut ratatui::Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(5),
            Constraint::Length(3),
        ])
        .split(f.area());

    render_header(f, chunks[0], app);
    render_main(f, chunks[1], app);
    render_status(f, chunks[2], app);

    if app.mode == Mode::Editing {
        render_edit_popup(f, app);
    }
    if app.mode == Mode::Help {
        render_help_popup(f);
    }
}

fn render_help_popup(f: &mut ratatui::Frame) {
    let area = centered_rect(60, 70, f.area());
    f.render_widget(Clear, area);

    let yellow = Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD);
    let dim = Style::default().fg(Color::DarkGray);
    let section = |s: &'static str| Line::from(Span::styled(s, yellow));
    let kb = |key: &'static str, desc: &'static str| {
        Line::from(vec![
            Span::styled(format!("  {key:<14}"), Style::default().fg(Color::Cyan)),
            Span::raw(desc),
        ])
    };

    let lines = vec![
        section("List mode"),
        kb("j / ↓", "Move selection down"),
        kb("k / ↑", "Move selection up"),
        kb("a", "Add a new link"),
        kb("e", "Edit selected link"),
        kb("d", "Delete selected link (confirm)"),
        kb("s", "Save changes to disk"),
        kb("?", "Toggle this help panel"),
        kb("q", "Quit (prompts if unsaved)"),
        Line::from(""),
        section("Edit mode"),
        kb("Tab", "Next field"),
        kb("Shift+Tab", "Previous field"),
        kb("Enter", "Commit edit (memory; press 's' to persist)"),
        kb("Esc", "Cancel edit"),
        Line::from(""),
        section("Confirm prompts"),
        kb("y / Y", "Confirm"),
        kb("any other", "Cancel"),
        Line::from(""),
        Line::from(Span::styled("Press Esc or '?' to close", dim)),
    ];

    let p = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(" Help — keybindings "),
        )
        .wrap(Wrap { trim: false });
    f.render_widget(p, area);
}

fn render_header(f: &mut ratatui::Frame, area: Rect, app: &App) {
    let dirty = if app.dirty { " [unsaved]" } else { "" };
    let title = format!(
        " links_tui — {}{} ({} links) ",
        app.path.display(),
        dirty,
        app.links.len()
    );
    let p = Paragraph::new(title).block(Block::default().borders(Borders::ALL));
    f.render_widget(p, area);
}

fn render_main(f: &mut ratatui::Frame, area: Rect, app: &mut App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(40), Constraint::Percentage(60)])
        .split(area);

    let items: Vec<ListItem> = app
        .links
        .iter()
        .enumerate()
        .map(|(i, l)| {
            ListItem::new(Line::from(vec![
                Span::styled(format!("{:>3} ", i + 1), Style::default().fg(Color::DarkGray)),
                Span::raw(l.nome.clone()),
            ]))
        })
        .collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title(" Links "))
        .highlight_style(
            Style::default()
                .bg(Color::Blue)
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )
        .highlight_symbol("▶ ");

    f.render_stateful_widget(list, cols[0], &mut app.state);

    let detail = match app.state.selected().and_then(|i| app.links.get(i)) {
        Some(l) => vec![
            Line::from(vec![
                Span::styled("Nome: ", Style::default().fg(Color::Yellow)),
                Span::raw(l.nome.clone()),
            ]),
            Line::from(vec![
                Span::styled("URL:  ", Style::default().fg(Color::Yellow)),
                Span::raw(l.url.clone()),
            ]),
            Line::from(vec![
                Span::styled("Tags: ", Style::default().fg(Color::Yellow)),
                Span::raw(l.tags.join(", ")),
            ]),
        ],
        None => vec![Line::from(Span::styled(
            "(no link selected — press 'a' to add)",
            Style::default().fg(Color::DarkGray),
        ))],
    };

    let p = Paragraph::new(detail)
        .block(Block::default().borders(Borders::ALL).title(" Detail "))
        .wrap(Wrap { trim: false });
    f.render_widget(p, cols[1]);
}

fn render_status(f: &mut ratatui::Frame, area: Rect, app: &App) {
    let p = Paragraph::new(app.status.clone())
        .block(Block::default().borders(Borders::ALL).title(" Status "));
    f.render_widget(p, area);
}

fn render_edit_popup(f: &mut ratatui::Frame, app: &App) {
    let Some(buf) = app.edit.as_ref() else { return };
    let area = centered_rect(70, 60, f.area());
    f.render_widget(Clear, area);

    let block = Block::default()
        .borders(Borders::ALL)
        .title(if buf.editing_index.is_some() {
            " Edit link "
        } else {
            " New link "
        });
    f.render_widget(block, area);

    let inner = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints([
            Constraint::Length(3),
            Constraint::Length(3),
            Constraint::Length(3),
            Constraint::Min(1),
        ])
        .split(area);

    let field_widget = |label: &str, value: &str, active: bool| -> Paragraph<'_> {
        let style = if active {
            Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)
        } else {
            Style::default()
        };
        let display = if active {
            format!("{value}_")
        } else {
            value.to_string()
        };
        Paragraph::new(display).block(
            Block::default()
                .borders(Borders::ALL)
                .title(format!(" {label} "))
                .border_style(style),
        )
    };

    f.render_widget(
        field_widget("Nome", &buf.nome, buf.field == Field::Nome),
        inner[0],
    );
    f.render_widget(
        field_widget("Tags (comma-separated)", &buf.tags, buf.field == Field::Tags),
        inner[1],
    );
    f.render_widget(
        field_widget("URL", &buf.url, buf.field == Field::Url),
        inner[2],
    );

    let hint = Paragraph::new(
        "Tab/Shift+Tab: switch field   Enter: save   Esc: cancel",
    )
    .style(Style::default().fg(Color::DarkGray));
    f.render_widget(hint, inner[3]);
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let v = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - percent_y) / 2),
            Constraint::Percentage(percent_y),
            Constraint::Percentage((100 - percent_y) / 2),
        ])
        .split(r);
    Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - percent_x) / 2),
            Constraint::Percentage(percent_x),
            Constraint::Percentage((100 - percent_x) / 2),
        ])
        .split(v[1])[1]
}
