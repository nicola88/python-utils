# MLOL scraper

*MLOL* is a software system running digital public libraries in Italy.

This script use _Selenium_ to navigate automatically the website and crawl public and private information.

## Requirements

- Python 3
- Selenium
- Firefox driver for Selenium

## Configuration

The configuration is passed as the first positional argument (see section _Usage_ for additional information). 

```json
{
  "url": "https://xxx.medialibrary.it",
  "user.name": "<your username>",
  "user.password": "<your password>",
  "reservations.max_concurrent": 5,
  "loans.duration_in_days": 15,
  "loans.max_monthly": 2
}
```

| Parameter                     | Description |
| ----------------------------- | ------------- |
| `url`                         | Website URL, e.g. https://example.medialibrary.it |
| `user.name`                   | Your username |
| `user.password`               | Your password |
| `reservations.max_concurrent` | Maximum number of concurrent eBook reservations allowed |
| `loans.duration_in_days`      | Duration of a loan (in days) |
| `loans.max_monthly`           | Maximum number of eBooks you can borrow each month |

## Usage

```bash
cd mlol-scraper
python mlol-scraper.py <path-to-JSON-config-file>
```