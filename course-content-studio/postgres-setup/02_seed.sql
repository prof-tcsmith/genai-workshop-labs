-- ===========================================================================
-- Course Content Studio — seed data (run AFTER 01_schema.sql)
-- ===========================================================================
-- Plain INSERTs only. IDs are explicit so foreign keys are easy to follow and
-- the file is re-runnable after a fresh 01_schema.sql load.
-- ===========================================================================

-- --- Courses ----------------------------------------------------------------
INSERT INTO courses (id, code, title, term) VALUES
  (1, 'ISM 6155', 'Data Management',                'Fall 2026'),
  (2, 'ISM 6021', 'Managing Information Systems',    'Fall 2026'),
  (3, 'ISM 6404', 'Business Intelligence & Analytics','Spring 2026');

-- --- Learning objectives (varied Bloom levels) ------------------------------
-- Course 1: ISM 6155 Data Management
INSERT INTO learning_objectives (id, course_id, text, bloom_level) VALUES
  (1, 1, 'Recall the components of the relational data model (relations, keys, constraints).', 'Remember'),
  (2, 1, 'Explain how normalization reduces redundancy and update anomalies.',                'Understand'),
  (3, 1, 'Design a normalized relational schema (3NF) for a given business domain.',          'Create'),
  (4, 1, 'Write SQL queries that join, filter, and aggregate across multiple tables.',         'Apply'),
  (5, 1, 'Evaluate trade-offs between relational and NoSQL stores for a workload.',            'Evaluate');

-- Course 2: ISM 6021 Managing Information Systems
INSERT INTO learning_objectives (id, course_id, text, bloom_level) VALUES
  (6,  2, 'Identify the major categories of enterprise information systems (ERP, CRM, SCM).',   'Remember'),
  (7,  2, 'Summarize how IT governance frameworks align IT with business strategy.',           'Understand'),
  (8,  2, 'Analyze a business process to locate bottlenecks and automation opportunities.',     'Analyze'),
  (9,  2, 'Recommend an IS sourcing strategy (build vs. buy vs. SaaS) for a scenario.',         'Evaluate');

-- Course 3: ISM 6404 Business Intelligence & Analytics
INSERT INTO learning_objectives (id, course_id, text, bloom_level) VALUES
  (10, 3, 'Define key BI concepts: data warehouse, star schema, ETL, and OLAP.',               'Remember'),
  (11, 3, 'Apply dimensional modeling to design a star schema for a reporting need.',          'Apply'),
  (12, 3, 'Interpret a dashboard to draw a defensible business recommendation.',               'Analyze');

-- --- Rubrics + criteria -----------------------------------------------------
-- One rubric per course; criteria carry a JSON levels map (level -> descriptor).
INSERT INTO rubrics (id, course_id, title) VALUES
  (1, 1, 'Database Design Project Rubric'),
  (2, 2, 'IS Strategy Case Analysis Rubric');

INSERT INTO rubric_criteria (id, rubric_id, criterion, levels_json) VALUES
  (1, 1, 'Schema correctness (keys & normalization)',
        '{"exemplary":"All tables in 3NF; keys and FKs correct and justified.","proficient":"Mostly 3NF; minor key or FK issues.","developing":"Redundancy or anomalies present; keys unclear.","beginning":"Schema does not capture the domain."}'),
  (2, 1, 'SQL quality',
        '{"exemplary":"Queries are correct, efficient, and well-commented.","proficient":"Queries correct with minor inefficiencies.","developing":"Some queries incorrect or overly complex.","beginning":"Queries fail or do not address the task."}'),
  (3, 1, 'Documentation & rationale',
        '{"exemplary":"Clear ERD and design decisions fully justified.","proficient":"ERD present; rationale mostly clear.","developing":"Sparse documentation.","beginning":"No meaningful documentation."}'),
  (4, 2, 'Problem analysis',
        '{"exemplary":"Root causes identified with strong evidence.","proficient":"Reasonable analysis with some support.","developing":"Surface-level analysis.","beginning":"Problem misidentified."}'),
  (5, 2, 'Recommendation & feasibility',
        '{"exemplary":"Actionable recommendation with cost/benefit and risks.","proficient":"Sound recommendation, limited feasibility detail.","developing":"Vague recommendation.","beginning":"No clear recommendation."}');

-- --- Question bank (multiple types) -----------------------------------------
INSERT INTO question_bank
  (id, course_id, objective_id, type, stem, options_json, correct_json, points, source) VALUES
  (1, 1, 3, 'mcq',
      'Which anomaly does converting a table to Third Normal Form (3NF) primarily eliminate?',
      '["Insertion, update, and deletion anomalies from transitive dependencies","Loss of referential integrity","Slow index scans","Deadlocks between transactions"]',
      '{"answer_index":0}', 5, 'seed'),
  (2, 1, 4, 'short_answer',
      'Write a SQL query that returns each course code and the number of learning objectives it has.',
      NULL,
      '{"answer":"SELECT c.code, COUNT(lo.id) FROM courses c LEFT JOIN learning_objectives lo ON lo.course_id = c.id GROUP BY c.code;"}',
      4, 'seed'),
  (3, 1, 2, 'true_false',
      'Normalization can increase the number of joins required to answer a query.',
      '["True","False"]',
      '{"answer":true}', 1, 'seed'),
  (4, 2, 6, 'mcq',
      'Which enterprise system category is primarily focused on managing customer interactions and sales pipelines?',
      '["ERP","CRM","SCM","DBMS"]',
      '{"answer_index":1}', 2, 'seed');

-- --- Content sources (provenance examples) ----------------------------------
INSERT INTO content_sources (id, course_id, filename, kind, chunk_count) VALUES
  (1, 1, 'ism6155_syllabus.pdf',     'syllabus', 12),
  (2, 1, 'relational_model_notes.md','reading',  34),
  (3, 2, 'ism6021_syllabus.pdf',     'syllabus', 10);

-- --- Keep serial sequences ahead of the explicit IDs above ------------------
SELECT setval('courses_id_seq',             (SELECT MAX(id) FROM courses));
SELECT setval('learning_objectives_id_seq', (SELECT MAX(id) FROM learning_objectives));
SELECT setval('rubrics_id_seq',             (SELECT MAX(id) FROM rubrics));
SELECT setval('rubric_criteria_id_seq',     (SELECT MAX(id) FROM rubric_criteria));
SELECT setval('question_bank_id_seq',       (SELECT MAX(id) FROM question_bank));
SELECT setval('content_sources_id_seq',     (SELECT MAX(id) FROM content_sources));
