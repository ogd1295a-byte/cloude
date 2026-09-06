# 用 Python、uv 與 GitHub Actions 建立定期檢查

這個專案是一份可以跟著做、再改成自己用途的範本。我們以「查詢臺大資訊系統訓練班的證書是否可以領取」為例，練習用 Python 讀取網頁、用 ntfy 發通知，再交給 GitHub Actions 定期執行。

完成後，即使自己的電腦沒有開機，GitHub Actions 也會依照排程執行程式，並把每次檢查的結果存進同一個 repository 的 `state` 分支。

目前的範例設定是檢查[第479期課程（6250）](https://train.csie.ntu.edu.tw/school/news/certificate.php?id=6250)，每天台灣時間 09:00～17:00 每整點執行一次。你可以先沿用這個課程，換成自己的通知 topic，再調整排程。

## 1. 建立自己的 repository

你需要 GitHub 帳號，以及本機的 Git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。Python 版本和套件由 uv 管理。

如果頁面上有 **Use this template**，選擇 **Create a new repository**，建立在自己的帳號下。不要勾選 **Include all branches**：只需要預設分支的程式，`state` 分支會在第一次執行時自動建立。[GitHub 範本使用說明](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)

也可以 Fork 這個 repository，只複製 `main` 分支。使用 Fork 時，請到自己 repository 的 **Actions** 頁面啟用 workflows，再確認 **Certificate monitor** 已啟用。

接著將自己的 repository 下載到電腦。以下的 `YOUR_ACCOUNT` 和 `YOUR_REPO` 都要換成自己的名稱：

```sh
git clone https://github.com/YOUR_ACCOUNT/YOUR_REPO.git
cd YOUR_REPO
```

## 2. 設定自己的通知

在 ntfy App 或 [ntfy 網頁](https://ntfy.sh) 訂閱一個自己取的 topic，並允許通知。接著打開 [check_certificate.py](check_certificate.py)，將 `TOPIC` 改成相同名稱：

```python
TOPIC = "你的-topic-名稱"
```

程式原本的 `aip479cert` 是這份範例使用的 topic。請在正式執行前改成自己的名稱，讓通知送到你訂閱的地方。

目前 [tests/test_certificate.py](tests/test_certificate.py) 的 `test_notification_payload_and_receipt` 也有一行檢查 topic：

```python
self.assertEqual(payload["topic"], "aip479cert")
```

將這裡的 `aip479cert` 一起改成自己的 topic，讓測試檢查你預期的通知目的地。

如果要查詢同一網站的其他期別，也要修改 `COURSE_URL` 和 `COURSE_TITLE`。標題必須與網頁上的完整課程標題一致，並記得更新 `notify()` 裡的通知標題。

## 3. 先在本機查詢一次

在專案資料夾執行：

```sh
uv run --locked python check_certificate.py --dry-run
```

uv 會建立 Python 環境並安裝 `uv.lock` 指定的套件。`--dry-run` 會讀取實際網頁、印出狀態，但不發通知，也不寫入紀錄。

確認能看到課程狀態後，再執行測試：

```sh
uv run --locked python -m unittest discover -s tests -v
```

測試不會連線到課程網站或 ntfy。若有失敗，先看錯誤訊息，確認修改的設定和測試是否一致。

需要在本機正式執行時，移除 `--dry-run`：

```sh
uv run --locked python check_certificate.py
```

只有狀態完整等於「已可領取證書」時才會通知；還沒開放時，沒有收到通知是正常的。本機紀錄會存到 `.state/`，與 GitHub Actions 的紀錄分開。

## 4. 設定 GitHub Actions 排程

打開 [.github/workflows/certificate.yml](.github/workflows/certificate.yml)，找到：

```yaml
on:
  schedule:
    - cron: '0 1-9 * * *'
  workflow_dispatch:
```

`schedule` 用來定期執行，`workflow_dispatch` 則讓你可以在 GitHub 網頁手動執行。

這份 workflow 沒有指定時區，因此 cron 使用 **UTC**。換算台灣時間（UTC+8）時，要先減 8 小時。Cron 的五個欄位依序是「分、時、日、月、星期」，`*` 代表每個值。

| 想要的台灣時間 | Cron（UTC） |
| --- | --- |
| 每天 09:00～17:00，每整點一次 | `0 1-9 * * *` |
| 每天 09:00 一次 | `0 1 * * *` |
| 每小時的第 17 分鐘 | `17 * * * *` |
| 週一到週五 09:00～17:00，每整點一次 | `0 1-9 * * 1-5` |

目前的設定包含週末及 17:00，每天共 9 次。GitHub 排程可能延遲，整點尤其可能遇到高負載，不保證準時執行。排程只會使用預設分支上的 workflow；公開 repository 若連續 60 天沒有活動，排程會自動停用。[GitHub 排程文件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 5. 推送並手動執行

將修改提交到自己的 repository：

```sh
git add check_certificate.py tests/test_certificate.py .github/workflows/certificate.yml
git commit -m "Configure my notification and schedule"
git push origin main
```

如果你的預設分支不是 `main`，請將指令中的分支名稱換成自己的預設分支。

到自己的 GitHub repository，依序選擇 **Actions → Certificate monitor → Run workflow**，選預設分支後執行。這份 workflow 只接受預設分支，從其他分支手動執行會略過工作。

第一次執行會建立 `state` 分支。打開該次執行的 **Check certificate and notify** 步驟，確認印出的課程狀態；再確認 **Commit this check to state branch** 成功。之後 GitHub 就會依照你的排程執行，不需要讓本機程式一直開著。

Workflow 已設定內建 `GITHUB_TOKEN` 的 `contents: write` 權限，不需要另外建立 token 或 secret。如果寫入分支時出現權限錯誤，請確認 repository／組織的 Actions 政策允許寫入，且 `state` 分支規則允許 Actions 直接提交。

## 查看執行紀錄

在 GitHub 的分支選單切換到 `state`，可以看到：

- `status.json`：最近一次檢查結果、是否通知過，以及通知時間。
- `history.jsonl`：每次檢查追加一行，包含 UTC 時間、網頁狀態、成功或失敗、錯誤訊息，以及該次 Actions 的 `run_url`。

每次檢查都會產生一筆 commit。即使狀態沒變或先前已通知過，仍會查詢並留下紀錄；已通知過就不再重複通知。程式留在 `main`，紀錄留在 `state`，不需要合併這兩個分支。

網站或 ntfy 發生可捕捉的錯誤時，也會保存失敗紀錄，Actions 仍顯示失敗。如果安裝套件或測試就失敗、runner 被中止，或紀錄推送失敗，`state` 可能沒有該次紀錄，此時請到 Actions 查看 log。

通知成功後若紀錄未能寫回 GitHub，下次可能再次通知。若想主動重發，可在 `state/status.json` 將 `notified` 改成 `false` 並移除 `notified_at`，提交後再執行。

已經跑過後才更換課程網址或 topic，舊紀錄會因設定不符而被拒絕。請先停用 workflow，在 `state` 分支移除舊的 `status.json` 並提交，再重新啟用；`history.jsonl` 可以保留。本機則移除 `.state/status.json` 後再執行。

## 改成自己的定期任務

這份範例每次只監控一個課程。若要改成其他網站，除了網址，還需要調整讀取與判斷方式：

| 檔案或函式 | 用途 |
| --- | --- |
| `check_certificate.py` 的 `fetch_page()` | 取得網頁內容 |
| `parse_status()` | 找到頁面中的狀態，目前使用 Beautiful Soup 解析課程標題與 `summary` |
| `check()` 與 `READY` | 判斷是否需要通知，並記錄執行結果 |
| `notify()` | 設定 ntfy 通知的標題、內容和連結 |
| `.github/workflows/certificate.yml` | 設定排程與執行指令 |
| `scripts/state_branch.sh` | 讀取、提交並推送 `state` 分支 |
| `tests/` | 驗證狀態判斷、通知與分支紀錄 |

建議先完成上面的範例，再修改一個部分，用 `--dry-run` 和測試確認結果，最後推送到 GitHub 手動執行一次。如果新增 Python 套件，使用 `uv add 套件名稱`，並把更新的 `pyproject.toml` 和 `uv.lock` 一起提交。
