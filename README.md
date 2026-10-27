# Fridge Scan

Fridge Scan helps users track fridge inventory, manage grocery lists,
and discover recipes using ingredients they already have.

## Planned architecture

- Python backend using FastAPI
- Responsive web interface
- Progressive Web App (PWA)
- Android APK using Capacitor
- SQLite for local development and PostgreSQL as a future deployment option

## Features

- Fridge photo uploads and camera capture
- Food recognition (currently a demo; real AI integration is pending)
- Inventory management
- Automatic low-stock grocery suggestions
- Recipe recommendations and missing-ingredient lists

## Privacy

Uploaded images should be processed temporarily and not stored permanently.
Database records should contain inventory, grocery items, and scan metadata,
not uploaded image files.

## Development status

This project is under active development. The website, PWA, Android package,
and real AI food recognition are not yet complete.
