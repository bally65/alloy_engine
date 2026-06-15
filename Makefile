# alloy_engine — 常用指令。裝置自動選 CUDA/MPS/CPU（見 alloy_engine/config.py）。
.PHONY: install test pipeline search figures recommend cost clean

install:        ## 安裝依賴（CPU torch；GPU 機器可改裝對應 wheel）
	pip install -e .

test:           ## 跑全套測試（290+）
	python -m pytest tests/ -q

pipeline:       ## 一鍵生產級全管線（合成→真實Tc→烘焙→Br對標→裝置對標）
	bash scripts/run_full_pipeline.sh

search:         ## 範例 GA 搜尋（150°C 廢熱，真實 Tc + Cu 複合）
	python scripts/run_search.py --scenario 低溫廢熱_150C \
	  --checkpoint alloy_engine/models/checkpoints/bundle_real_tc.pt \
	  --mode thermomagnetic --w-device 1.0 --device-matrix Cu \
	  --population-size 20000 --n-generations 40 --output-dir results/case_150C

figures:        ## 產出版級圖表包 → docs/figures/
	python scripts/make_figure_pack.py

recommend:      ## 端到端材料推薦（預設 80°C, 2T）
	python scripts/recommend_material.py

cost:           ## 最低成本材料分析
	python scripts/lowest_cost_material.py

clean:          ## 清除快取與暫存
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf results/_*.log

help:           ## 顯示本說明
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
