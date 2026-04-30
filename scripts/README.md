# Scripts Index

## Current workflow

- `update_hainan_forecast.py`
  Download tomorrow's Hainan forecast, score it, archive it under `data/collections/hainan/YYYY-MM-DD/`, and publish the latest web data.
- `score_china_forecast.py`
  Turn an Open-Meteo forecast CSV into the web map JSON. Also computes `west_low_cloud_index` for sunset scoring.
- `sunset_grid_score.py`
  Current grid-cell sunset scoring rules used by the web app.
- `download_open_meteo_tile_forecast.py`
  Download high-resolution Open-Meteo ECMWF forecast tiles for a small region such as Hainan.
- `download_open_meteo_china_forecast.py`
  Download coarse sampled Open-Meteo ECMWF forecast points for a large region such as China.

## Modeling preparation

- `download_era5_truth.py`
  Download ERA5 truth weather data for labels and evaluation.
- `download_recent_era5_truth.py`
  Download the most recent available three months of ERA5 truth weather. By default it uses all 24 UTC hours and automatically steps back 5 days to avoid ERA5 latency.
- `convert_era5_grib_to_csv.py`
  Flatten ERA5 GRIB output into a CSV table keyed by `valid_time_utc`, `latitude`, and `longitude`.
- `download_open_meteo_historical_forecast.py`
  Download historical Open-Meteo forecast point series for model input backfill.
- `build_training_table.py`
  Merge forecast data and truth data into a training table.
- `modeling_config.py`
  Shared modeling defaults such as target site and feature columns.
- `sunset_rules.py`
  Early point-level label rules used by `build_training_table.py`.

## Utilities

- `check_data_access.py`
  Validate local dependencies and CDS credential readiness.

## Legacy

- `legacy/download_open_forecast.py`
  Early ECMWF Open Data GRIB downloader kept for reference. It is not part of the current web update path.
