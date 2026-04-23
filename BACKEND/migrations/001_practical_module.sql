-- =============================================================
-- Migration 001: Practical Learning Module
-- Run this in the Supabase SQL Editor
-- =============================================================

-- 1. Add tipo column to asignaturas
ALTER TABLE asignaturas
  ADD COLUMN IF NOT EXISTS tipo text DEFAULT 'teorica'
  CHECK (tipo IN ('teorica', 'practica', 'mixta'));

-- 1b. Manual override flag — when true, auto-detect won't overwrite tipo.
-- Set to true by PUT /asignaturas when the user explicitly changes tipo in Ajustes.
ALTER TABLE asignaturas
  ADD COLUMN IF NOT EXISTS tipo_manual boolean DEFAULT false;

-- 2. Table: formulas_tema
CREATE TABLE IF NOT EXISTS formulas_tema (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asignatura_id uuid REFERENCES asignaturas(id) ON DELETE CASCADE,
  documento_id  uuid REFERENCES documentos(id)  ON DELETE CASCADE,
  tema          text,
  nombre        text,
  latex         text,
  variables     jsonb DEFAULT '[]'::jsonb,
  created_at    timestamptz DEFAULT now()
);

-- 3. Table: ejercicios
CREATE TABLE IF NOT EXISTS ejercicios (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asignatura_id uuid REFERENCES asignaturas(id) ON DELETE CASCADE,
  documento_id  uuid REFERENCES documentos(id)  ON DELETE CASCADE,
  tema          text,
  tipo          text,
  enunciado     jsonb DEFAULT '[]'::jsonb,
  solucion      jsonb DEFAULT '[]'::jsonb,
  dades         jsonb DEFAULT '[]'::jsonb,
  dificultad    int  DEFAULT 1 CHECK (dificultad BETWEEN 1 AND 3),
  created_at    timestamptz DEFAULT now()
);

-- 4. Table: practica_resultados (track per-exercise correctness)
CREATE TABLE IF NOT EXISTS practica_resultados (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id    uuid REFERENCES usuarios(id) ON DELETE CASCADE,
  ejercicio_id  uuid REFERENCES ejercicios(id) ON DELETE CASCADE,
  correcto      boolean NOT NULL,
  created_at    timestamptz DEFAULT now()
);

-- 5. Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_formulas_asignatura  ON formulas_tema(asignatura_id);
CREATE INDEX IF NOT EXISTS idx_formulas_documento   ON formulas_tema(documento_id);
CREATE INDEX IF NOT EXISTS idx_ejercicios_asignatura ON ejercicios(asignatura_id);
CREATE INDEX IF NOT EXISTS idx_ejercicios_documento  ON ejercicios(documento_id);
CREATE INDEX IF NOT EXISTS idx_ejercicios_tipo       ON ejercicios(tipo);
CREATE INDEX IF NOT EXISTS idx_practica_usuario      ON practica_resultados(usuario_id);
