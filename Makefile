PY := .venv/bin/python
GUI := tools/catanatron-gui
SEED ?= 1

.PHONY: test smoke validate match run board gui gui-stop

test:
	$(PY) -m pytest -q

smoke:
	$(PY) -m src.sim.smoke $(or $(GAMES),100)

validate:
	$(PY) -m src.sim.validate_production $(or $(GAMES),1000)

match:
	$(PY) -m src.sim.match $(or $(A),greedy) $(or $(B),random) --pairs $(or $(PAIRS),100)

run:
	$(PY) -m src.sim.runs $(or $(NAME),run) $(or $(A),greedy) $(or $(B),random) --pairs $(or $(PAIRS),100) $(if $(START),--start $(START))

board:
	$(PY) -m src.analysis.board_plot --seed $(SEED) $(if $(MOVES),--moves $(MOVES)) $(if $(A),--a $(A)) $(if $(B),--b $(B)) --out data/boards/board.png
	open data/boards/board.png

gui: gui-stop
	$(GUI)/start-gui.sh

gui-stop:
	-@pkill -f "flask run --port 5001"; pkill -f "vite --port 3000"; true
