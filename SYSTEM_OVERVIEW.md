# hamada_offshore_current システム概要

作成日: 2026-05-09 JST  
作業フォルダ: `C:\Codex\Dev\hamada_offshore_current`  
GitHubリポジトリ: `https://github.com/supergonti/hamada_offshore_current`  
GitHub Pages: `https://supergonti.github.io/hamada_offshore_current/hamada_offshore_current.html`

## 目的

室戸沖版の潮流ダッシュボードを参考に、浜田沖・高島沖・見島沖の潮流、水温、塩分をWeb上で確認できるGitHub Pages向けの静的HTMLシステムを作成した。

このプロジェクトはCodex移行テスト用として開始したが、現在はCopernicus Marine / CMEMS の実データをGitHub Actionsで毎朝取得し、公開CSVを更新する構成になっている。

## 対象地点

| 表示名 | 緯度 | 経度 | 元座標 |
|---|---:|---:|---|
| 浜田沖 | 34.923889 | 132.013278 | 34°55'26.0"N 132°00'47.8"E |
| 高島沖 | 34.845861 | 131.820278 | 34°50'45.1"N 131°49'13.0"E |
| 見島沖 | 34.951972 | 131.077111 | 34°57'07.1"N 131°04'37.6"E |

## 主要ファイル

| ファイル | 役割 |
|---|---|
| `hamada_offshore_current.html` | GitHub Pagesで表示する本体HTML。Chart.jsとLeafletをCDNから読み込む |
| `data/hamada_offshore_current_all.csv` | 公開用の実データCSV。3地点を `point` 列で区別する |
| `scripts/update_hamada_current.py` | Copernicus Marineから潮流、水温、塩分を取得してCSVへ追記するPythonスクリプト |
| `.github/workflows/update_hamada_current.yml` | 毎朝06:30 JSTにデータ取得を実行するGitHub Actions |
| `requirements.txt` | Actionsで使うPython依存関係 |
| `README.md` | 簡易説明 |
| `SYSTEM_OVERVIEW.md` | この引き継ぎ用システム概要 |

## 画面仕様

- ページタイトルは「浜田沖 潮流ダッシュボード」
- 「潮流ビューア」セクション内に地点切り替えボタンを配置
  - 浜田沖
  - 高島沖
  - 見島沖
- 「潮流ビューア」という表示名は変更しない
- グラフは2つ
  - 流速、流向矢印、水温
  - 塩分
- 流速グラフの表示範囲は `0から2.0 kn`
- 流速データポイント上に流向矢印を表示
- 表には日付、流向、流速、m/s、水温、塩分を表示
- ダッシュボード、潮流ビューア、欠測データチェッカー、データ読み込みは折りたたみ可能
- ページ初期表示ではダッシュボードとデータ読み込みは閉じた状態
- データ読み込みセクションはページ最下部に配置
- CSVドラッグ＆ドロップで手元CSVを一時的に読み込める

## データ仕様

CSVパス:

```text
data/hamada_offshore_current_all.csv
```

列:

```text
date,point,lat,lon,u_ms,v_ms,speed_ms,speed_kn,direction,temp_c,salinity
```

主な意味:

| 列 | 意味 |
|---|---|
| `date` | 日付。例: `2026-05-07` |
| `point` | 地点名。`浜田沖`、`高島沖`、`見島沖` |
| `lat` / `lon` | 対象地点座標 |
| `u_ms` / `v_ms` | 東西、南北流速成分 |
| `speed_ms` | 流速 m/s |
| `speed_kn` | 流速 kn |
| `direction` | 流向。度数 |
| `temp_c` | 水温 |
| `salinity` | 塩分 |

2026-05-08時点で、以下の90日分を取得済み。

| 地点 | 行数 | 開始日 | 最終日 |
|---|---:|---|---|
| 浜田沖 | 90 | 2026-02-07 | 2026-05-07 |
| 高島沖 | 90 | 2026-02-07 | 2026-05-07 |
| 見島沖 | 90 | 2026-02-07 | 2026-05-07 |

浜田沖と高島沖は近い海域のため傾向が似るが、CSV比較では90日中完全一致は0日で、同一データではないことを確認済み。

## データ取得

取得元は Copernicus Marine / CMEMS。

GitHub ActionsではRepository secretsを使用する。

必要なsecrets:

```text
CMEMS_USERNAME
CMEMS_PASSWORD
```

Python側では以下の環境変数として使用される。

```text
COPERNICUSMARINE_SERVICE_USERNAME
COPERNICUSMARINE_SERVICE_PASSWORD
```

使用データセット:

| 用途 | dataset id |
|---|---|
| 2025-12-31以前の再解析 | `cmems_mod_glo_phy_my_0.083deg_P1D-m` |
| 2026-01-01以降の潮流 | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` |
| 2026-01-01以降の水温 | `cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m` |
| 2026-01-01以降の塩分 | `cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m` |

スクリプトは当初1日ずつAPI取得していたが、90日取得が遅すぎたため、現在は期間まとめ取得に変更済み。90日×3地点のバックフィルは約2分50秒で成功した。

## GitHub Actions

Workflow:

```text
.github/workflows/update_hamada_current.yml
```

自動実行:

```text
毎日 06:30 JST
```

手動実行も可能。

主な入力:

| 入力 | 用途 |
|---|---|
| `target_date` | 1日だけ取得 |
| `start_date` / `end_date` | 期間指定で取得 |
| `collect_all=true` | 2022-01-01から昨日まで全再構築。重いので注意 |

90日前から昨日までを再取得する例:

```text
start_date=2026-02-07
end_date=2026-05-07
```

既存の `date + point` はスキップされる。欠けている地点や日付だけ追加される。

## Git操作と公開

現在のローカルフォルダ:

```text
C:\Codex\Dev\hamada_offshore_current
```

GitHub remote:

```text
origin https://github.com/supergonti/hamada_offshore_current.git
```

ブランチ:

```text
master
```

公開URL:

```text
https://supergonti.github.io/hamada_offshore_current/hamada_offshore_current.html
```

push前には必ず3層スキャンを実行する。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Program Files\Git\bin\bash.exe' 'C:\Claude\tools\scan_3layer.sh' 'C:\Codex\Dev\hamada_offshore_current'
```

## 直近の主要コミット

| コミット | 内容 |
|---|---|
| `d9719ef` | 流速グラフ上限を2.0 knに変更 |
| `60c0d8e` | GitHub Actionsによる3地点CSV更新 |
| `1100715` | 期間まとめ取得に高速化 |
| `eab842b` | 3地点切り替えと3地点データ取得に対応 |
| `32c3472` | データ読み込み欄を下部へ移動 |

## 名称移行メモ

- 2026-05-09にローカル作業フォルダを `C:\Codex\Dev\hamada_offshore_current` に移行
- 2026-05-09にGitHubリポジトリ名をテスト用名称から `hamada_offshore_current` へ変更
- GitHub Pages URLも `https://supergonti.github.io/hamada_offshore_current/hamada_offshore_current.html` へ変更
- 旧テスト用フォルダは不要になったため削除対象

## 注意点

- Actionsログに Node.js 20 deprecation の警告が出たが、2026-05-08時点では動作成功済み
- Chart.jsとLeafletはCDN依存のため、オフラインでは完全表示できない
- 実データCSVが存在しない場合、HTMLはデモデータへフォールバックする

## 次セッションで最初に確認すること

1. `C:\Codex\Dev\hamada_offshore_current` を作業フォルダとして開く
2. `git status --short` で未保存変更を確認
3. GitHub Pagesを開く
4. 地点ボタンで浜田沖、高島沖、見島沖を切り替え、グラフと表が変わることを確認
5. Actionsの最新実行が成功しているか確認

