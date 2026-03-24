CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    filetype TEXT NOT NULL,
    level1 TEXT,
    level2 TEXT,
    level3 TEXT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);