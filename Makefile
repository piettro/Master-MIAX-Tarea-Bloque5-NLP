# Envoltorio fino sobre `scripts/tareas.py`.
#
# La lógica vive en Python y no aquí a propósito: las tres máquinas del grupo
# son Windows, macOS y Linux, y en Windows no hay `make`. Quien no lo tenga
# ejecuta exactamente lo mismo con `python scripts/tareas.py <objetivo>`.
# Un solo sitio, ningún riesgo de que el Makefile y el script se separen.

PY ?= python
TAREAS := $(PY) scripts/tareas.py

.PHONY: help setup lint format tipos test cobertura baseline final informe \
        ablacion validar-golden reconstruir-secciones limpiar

help:            ## Lista los objetivos disponibles
	@$(TAREAS) --lista

setup:           ## Crea el entorno e instala el paquete en modo editable
	@$(TAREAS) setup

lint:            ## ruff (lint + formato) y mypy --strict sobre src/
	@$(TAREAS) lint

format:          ## Aplica el formateo de ruff
	@$(TAREAS) format

tipos:           ## Solo mypy --strict
	@$(TAREAS) tipos

test:            ## pytest
	@$(TAREAS) test

cobertura:       ## pytest con informe de cobertura
	@$(TAREAS) cobertura

baseline:        ## Ejecuta el baseline del profesor y lo CONGELA
	@$(TAREAS) baseline

final:           ## Ejecuta el sistema final sobre el golden set
	@$(TAREAS) final

informe:         ## Regenera todas las tablas del informe desde resultados/
	@$(TAREAS) informe

ablacion:        ## Regenera la tabla de ablación del retrieval
	@$(TAREAS) ablacion

validar-golden:  ## Valida golden/golden_set.jsonl
	@$(TAREAS) validar-golden

reconstruir-secciones: ## Deriva secciones.jsonl desde los chunks
	@$(TAREAS) reconstruir-secciones

limpiar:         ## Borra cachés de herramientas y de embeddings
	@$(TAREAS) limpiar
