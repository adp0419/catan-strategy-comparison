PY := .venv/bin/python
GUI := ../catanatron-gui
SEED ?= 1

.PHONY: test smoke validate board gui gui-stop

test:
	$(PY) -m pytest -q

smoke:
	$(PY) -m src.sim.smoke $(or $(GAMES),100)

validate:
	$(PY) -m src.sim.validate_production $(or $(GAMES),1000)

board:
	$(PY) -m src.analysis.board_plot --seed $(SEED) $(if $(MOVES),--moves $(MOVES)) --out data/boards/board.png
	open data/boards/board.png

gui: gui-stop
	$(GUI)/start-gui.sh

gui-stop:
	-@pkill -f "flask run --port 5001"; pkill -f "vite --port 3000"; true
