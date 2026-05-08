# TEST02

Codex GitHub upload and web deployment test project.

Target output:
- hamada_offshore_current.html

Local preview:
- http://127.0.0.1:8002/hamada_offshore_current.html

GitHub Pages:
- https://supergonti.github.io/TEST02/hamada_offshore_current.html

Real data:
- Put the published current CSV at `data/hamada_offshore_current_all.csv`.
- The page tries that CSV first, then falls back to demo data only when the CSV is missing.
- Supported columns:
  - `date,speed_kn,speed_ms,direction,temp_c,salinity`
  - `date,point,lat,lon,u_ms,v_ms,speed_ms,speed_kn,direction,temp_c,salinity`

Daily update on GitHub:
- `.github/workflows/update_hamada_current.yml` runs every day at 06:30 JST.
- It fetches Hamada offshore data from Copernicus Marine and commits `data/hamada_offshore_current_all.csv`.
- Required GitHub repository secrets:
  - `CMEMS_USERNAME`
  - `CMEMS_PASSWORD`
- Manual run is available from GitHub Actions. Use `target_date` for one day, or `collect_all=true` only for a full rebuild.

Reference:
- C:\Dev\fishing-system Muroto\muroto_offshore_current.html
