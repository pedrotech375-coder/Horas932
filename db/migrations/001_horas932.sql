CREATE TABLE IF NOT EXISTS periodos_932 (
  periodo VARCHAR(20) NOT NULL,
  grupo SMALLINT UNSIGNED NOT NULL,
  fecha_fin_regular DATE NOT NULL,
  fecha_fin_calculo DATE NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (periodo, grupo),
  KEY idx_periodos_grupo_activo (grupo, activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS materias_932 (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  periodo VARCHAR(20) NOT NULL,
  grupo SMALLINT UNSIGNED NOT NULL,
  materia VARCHAR(255) NOT NULL,
  lunes_horas DECIMAL(5,2) NOT NULL DEFAULT 0,
  martes_horas DECIMAL(5,2) NOT NULL DEFAULT 0,
  miercoles_horas DECIMAL(5,2) NOT NULL DEFAULT 0,
  jueves_horas DECIMAL(5,2) NOT NULL DEFAULT 0,
  viernes_horas DECIMAL(5,2) NOT NULL DEFAULT 0,
  horas_totales_semana DECIMAL(5,2) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_materias_periodo_grupo_nombre (periodo, grupo, materia),
  CONSTRAINT fk_materias_periodo_932 FOREIGN KEY (periodo, grupo)
    REFERENCES periodos_932 (periodo, grupo) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS calendario_932 (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  periodo VARCHAR(20) NOT NULL,
  grupo SMALLINT UNSIGNED NOT NULL,
  tipo VARCHAR(40) NOT NULL,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  descripcion VARCHAR(255) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_calendario_evento (periodo, grupo, tipo, fecha_inicio, fecha_fin, descripcion),
  KEY idx_calendario_periodo_fecha (periodo, grupo, fecha_inicio),
  CONSTRAINT fk_calendario_periodo_932 FOREIGN KEY (periodo, grupo)
    REFERENCES periodos_932 (periodo, grupo) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO periodos_932
  (periodo, grupo, fecha_fin_regular, fecha_fin_calculo, activo)
VALUES ('2026-2', 932, '2026-11-30', '2026-12-11', 1);

INSERT IGNORE INTO materias_932
  (periodo, grupo, materia, lunes_horas, martes_horas, miercoles_horas, jueves_horas, viernes_horas, horas_totales_semana)
VALUES
  ('2026-2', 932, 'Análisis de Procesos y Datos de Negocios', 0, 0, 0, 0, 2, 2),
  ('2026-2', 932, 'Estadística Inferencial', 1, 0, 1, 1, 0, 3),
  ('2026-2', 932, 'Fundamentos de Metodología de la Investigación', 0, 0, 0, 2, 0, 2),
  ('2026-2', 932, 'Fundamentos de Redes', 0, 0, 2, 0, 2, 4),
  ('2026-2', 932, 'Lógica para los negocios', 2, 0, 1, 0, 0, 3),
  ('2026-2', 932, 'Programación', 2, 2, 0, 2, 0, 6),
  ('2026-2', 932, 'Sistemas de Información para Inteligencia de Negocios', 0, 2, 0, 0, 0, 2);

INSERT IGNORE INTO calendario_932
  (periodo, grupo, tipo, fecha_inicio, fecha_fin, descripcion)
VALUES
  ('2026-2', 932, 'adicional', '2026-12-09', '2026-12-09', 'Fecha adicional de clases'),
  ('2026-2', 932, 'adicional', '2026-12-10', '2026-12-10', 'Fecha adicional de clases'),
  ('2026-2', 932, 'adicional', '2026-12-11', '2026-12-11', 'Fecha adicional de clases'),
  ('2026-2', 932, 'suspension_laboral', '2026-11-02', '2026-11-02', 'Suspensión laboral'),
  ('2026-2', 932, 'suspension_laboral', '2026-11-16', '2026-11-16', 'Suspensión laboral'),
  ('2026-2', 932, 'suspension_laboral', '2026-12-18', '2026-12-18', 'Suspensión laboral'),
  ('2026-2', 932, 'examen_ordinario', '2026-11-30', '2026-12-08', 'Exámenes ordinarios y de competencias'),
  ('2026-2', 932, 'examen_extraordinario', '2026-12-14', '2026-12-17', 'Exámenes extraordinarios');
