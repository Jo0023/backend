-- =====================================================
-- SCRIPT DE CRÉATION DE PROJETS DE TEST
-- 2 projets par type : product, technical, research
-- =====================================================

-- ========== 1. SUPPRIMER LES DONNÉES EXISTANTES (optionnel) ==========
-- ATTENTION : Cela supprime les anciens projets et leurs données associées
-- Si vous voulez conserver les anciens, commentez cette section

-- Supprimer les évaluations et sessions associées
DELETE FROM criterion_scores;
DELETE FROM commission_evaluations;
DELETE FROM peer_evaluations;
DELETE FROM presentation_sessions;
DELETE FROM presentation_schedule;
DELETE FROM project_participation;
DELETE FROM project;

-- Réinitialiser les séquences
ALTER SEQUENCE project_id_seq RESTART WITH 1;
ALTER SEQUENCE project_participation_id_seq RESTART WITH 1;
ALTER SEQUENCE presentation_sessions_id_seq RESTART WITH 1;
ALTER SEQUENCE presentation_schedule_id_seq RESTART WITH 1;
ALTER SEQUENCE commission_evaluations_id_seq RESTART WITH 1;
ALTER SEQUENCE peer_evaluations_id_seq RESTART WITH 1;
ALTER SEQUENCE criterion_scores_id_seq RESTART WITH 1;


-- ========== 2. UTILISATEURS ==========
-- Les utilisateurs existants (1-28) sont conservés
-- Enseignant: ID 1
-- Leaders: IDs 2, 3, 4, 5, 6, 7
-- Membres: IDs 8-25
-- Commission: IDs 26, 27, 28


-- ========== 3. PROJETS PRODUCT ==========

-- Projet 1: Application Mobile de Livraison (Product)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (1, 'Application Mobile de Livraison', 2, 
        'Application de livraison de repas avec géolocalisation en temps réel, suivi des livreurs et notifications push. Interface utilisateur intuitive avec évaluation des restaurants et des livreurs.',
        4, 'product', NOW(), NOW());

-- Projet 2: Plateforme E-commerce Éco-responsable (Product)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (2, 'Plateforme E-commerce Éco-responsable', 2,
        'Site de vente en ligne avec recommandations personnalisées basées sur l''impact carbone. Intégration de critères écologiques, calcul de l''empreinte carbone des produits.',
        4, 'product', NOW(), NOW());


-- ========== 4. PROJETS TECHNICAL ==========

-- Projet 3: API Gateway pour Microservices (Technical)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (3, 'API Gateway pour Microservices', 3,
        'Gateway API unifiée avec authentification JWT, routage intelligent, rate limiting et monitoring. Support des protocoles REST et GraphQL avec cache distribué.',
        4, 'technical', NOW(), NOW());

-- Projet 4: Base de données distribuée NoSQL (Technical)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (4, 'Base de données distribuée NoSQL', 3,
        'Système de base de données NoSQL avec réplication multi-master, tolérance aux pannes et requêtes distribuées. Support des transactions ACID pour les opérations critiques.',
        4, 'technical', NOW(), NOW());


-- ========== 5. PROJETS RESEARCH ==========

-- Projet 5: IA pour la détection de fraudes (Research)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (5, 'IA pour la détection de fraudes bancaires', 4,
        'Modèle de Machine Learning pour détecter les transactions frauduleuses en temps réel. Utilisation de techniques d''apprentissage supervisé et non supervisé avec analyse des patterns comportementaux.',
        4, 'research', NOW(), NOW());

-- Projet 6: Analyse de sentiments sur réseaux sociaux (Research)
INSERT INTO project (id, name, author_id, description, max_participants, project_type, created_at, updated_at)
VALUES (6, 'Analyse de sentiments sur réseaux sociaux', 4,
        'Étude et modélisation des opinions sur Twitter et autres plateformes. Utilisation de NLP, analyse de lexiques et modèles transformer pour la classification des sentiments en temps réel.',
        4, 'research', NOW(), NOW());


-- ========== 6. PARTICIPATIONS (ÉQUIPES) ==========

-- Projet 1 (Product) - Équipe Marie (ID 2)
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(1, 5, NOW(), NOW()),   -- Jean
(1, 6, NOW(), NOW()),   -- Lucie
(1, 7, NOW(), NOW());   -- Pierre

-- Projet 2 (Product) - Équipe Marie (ID 2) - deuxième équipe
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(2, 8, NOW(), NOW()),   -- Emma
(2, 9, NOW(), NOW()),   -- Louis
(2, 10, NOW(), NOW());  -- Chloe

-- Projet 3 (Technical) - Équipe Thomas (ID 3)
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(3, 11, NOW(), NOW()),  -- Hugo
(3, 12, NOW(), NOW()),  -- Lea
(3, 13, NOW(), NOW());  -- Maxime

-- Projet 4 (Technical) - Équipe Thomas (ID 3) - deuxième équipe
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(4, 14, NOW(), NOW()),  -- Camille
(4, 15, NOW(), NOW()),  -- Antoine
(4, 16, NOW(), NOW());  -- Clara

-- Projet 5 (Research) - Équipe Nina (ID 4)
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(5, 17, NOW(), NOW()),  -- Nina
(5, 18, NOW(), NOW()),  -- Raphael
(5, 19, NOW(), NOW());  -- Sarah

-- Projet 6 (Research) - Équipe Nina (ID 4) - deuxième équipe
INSERT INTO project_participation (project_id, participant_id, created_at, updated_at)
VALUES
(6, 20, NOW(), NOW()),  -- Julien
(6, 21, NOW(), NOW()),  -- Manon
(6, 22, NOW(), NOW());  -- Alexis


-- ========== 7. VÉRIFICATIONS ==========

-- Afficher les projets créés
SELECT id, name, project_type, author_id FROM project ORDER BY id;

-- Afficher les participations
SELECT p.id, p.name, COUNT(pp.participant_id) as nb_members 
FROM project p 
LEFT JOIN project_participation pp ON pp.project_id = p.id 
GROUP BY p.id 
ORDER BY p.id;

-- Afficher tous les utilisateurs avec leur rôle
SELECT id, first_name, last_name, email FROM "user" ORDER BY id;


-- ========== 8. MISE À JOUR DES SÉQUENCES ==========

SELECT setval('project_id_seq', (SELECT MAX(id) FROM project));
SELECT setval('project_participation_id_seq', (SELECT MAX(id) FROM project_participation));


-- ========== 9. RÉSUMÉ ==========
\echo '=========================================='
\echo 'PROJETS CRÉÉS'
\echo '=========================================='
\echo ''
\echo 'Projet 1 (product) - Chef: Marie (ID 2)'
\echo '  Membres: Jean (5), Lucie (6), Pierre (7)'
\echo ''
\echo 'Projet 2 (product) - Chef: Marie (ID 2)'
\echo '  Membres: Emma (8), Louis (9), Chloe (10)'
\echo ''
\echo 'Projet 3 (technical) - Chef: Thomas (ID 3)'
\echo '  Membres: Hugo (11), Lea (12), Maxime (13)'
\echo ''
\echo 'Projet 4 (technical) - Chef: Thomas (ID 3)'
\echo '  Membres: Camille (14), Antoine (15), Clara (16)'
\echo ''
\echo 'Projet 5 (research) - Chef: Nina (ID 4)'
\echo '  Membres: Raphael (17), Sarah (18), Lucas (19)'
\echo ''
\echo 'Projet 6 (research) - Chef: Nina (ID 4)'
\echo '  Membres: Julien (20), Manon (21), Alexis (22)'
\echo ''
\echo 'Commission: Claire (26), Thomas (27), Julie (28)'
\echo 'Enseignant: Pierre (1)'
\echo '=========================================='