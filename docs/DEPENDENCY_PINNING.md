# 相依套件鎖定與供應鏈衛生 (Dependency Pinning)

> P1-c / F-DEP-01~03。目標：把「最低版本下限（`>=`）」升級為「可重現、抗竄改」的
> hash-pinned 安裝，讓 CI 與本地環境位元一致，並阻擋 typosquat / 套件被竄改。

## 為何需要

`requirements.txt` / `pyproject.toml` 目前用 `>=` 下限，每次安裝可能解析到不同版本
（不可重現），且無 hash 驗證（無法偵測 PyPI 上的套件被替換）。lockfile + `--require-hashes`
可同時解決兩者。

## 產生 lockfile（擇一）

### 方案 A：uv（推薦，最快）

```bash
# 安裝 uv：https://docs.astral.sh/uv/
uv pip compile requirements.txt -o requirements.lock --generate-hashes
# 開發/notebook 額外套件
uv pip compile pyproject.toml --extra docs --extra notebook -o requirements-dev.lock --generate-hashes
```

### 方案 B：pip-tools

```bash
pip install pip-tools
pip-compile requirements.txt -o requirements.lock --generate-hashes
```

> torch 常需指定索引（CPU 版）：
> `--index-url https://download.pytorch.org/whl/cpu`，或在 lock 後於 CI 以
> `--extra-index-url` 安裝對應 wheel。

## 安裝（驗證 hash）

```bash
pip install --require-hashes -r requirements.lock
```

任何套件 hash 不符即拒裝（偵測竄改 / 中間人 / typosquat）。

## CI 接線

把兩個 workflow 的安裝步驟由

```yaml
pip install numpy pandas scikit-learn matplotlib
```

改為

```yaml
pip install --require-hashes -r requirements.lock
```

並把 `requirements.lock` 納入版控、由 Dependabot 定期更新。

## 維護

- 升級套件：改 `requirements.txt` 的下限 → 重跑 compile → commit 新 lock。
- 啟用 GitHub Dependabot（`.github/dependabot.yml`）監看 `pip` 與 `github-actions`。
- 把第三方 GitHub Actions 由 `@v4` 改釘 commit SHA（F-CI-02，P2）。
