PY := .venv/bin/python
GUI := ../catanatron-gui
SEED ?= 1
GAMES ?= 100

.PHONY: test smoke board gui gui-stop

test:
	$(PY) -m pytest -q

smoke:
	$(PY) -m src.sim.smoke $(GAMES)

board:
	$(PY) -m src.analysis.board_plot --seed $(SEED) $(if $(MOVES),--moves $(MOVES)) --out data/boards/board.png
	open data/boards/board.png

gui: gui-stop
	$(GUI)/start-gui.sh

gui-stop:
	-@pkill -f "flask run --port 5001"; pkill -f "vite --port 3000"; true
