-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1
-- Généré le : mar. 05 mai 2026 à 12:39
-- Version du serveur : 10.4.32-MariaDB
-- Version de PHP : 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `alia_db`
--

-- --------------------------------------------------------

--
-- Structure de la table `assignments`
--

CREATE TABLE `assignments` (
  `id` int(11) NOT NULL,
  `delegue_id` int(11) NOT NULL,
  `medicament_id` int(11) NOT NULL,
  `score_module1` int(11) NOT NULL DEFAULT 0,
  `score_module2` int(11) NOT NULL DEFAULT 0,
  `score_module3` int(11) NOT NULL DEFAULT 0,
  `score_global` int(11) NOT NULL DEFAULT 0,
  `statut` enum('en_cours','termine','non_commence') NOT NULL DEFAULT 'non_commence',
  `assigned_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `assignments`
--

INSERT INTO `assignments` (`id`, `delegue_id`, `medicament_id`, `score_module1`, `score_module2`, `score_module3`, `score_global`, `statut`, `assigned_at`, `updated_at`) VALUES
(1, 2, 1, 0, 0, 0, 0, 'en_cours', '2026-05-05 09:56:58', '2026-05-05 09:56:58');

-- --------------------------------------------------------

--
-- Structure de la table `auth_group`
--

CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL,
  `name` varchar(150) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_group_permissions`
--

CREATE TABLE `auth_group_permissions` (
  `id` bigint(20) NOT NULL,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_permission`
--

CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `auth_permission`
--

INSERT INTO `auth_permission` (`id`, `name`, `content_type_id`, `codename`) VALUES
(1, 'Can add permission', 1, 'add_permission'),
(2, 'Can change permission', 1, 'change_permission'),
(3, 'Can delete permission', 1, 'delete_permission'),
(4, 'Can view permission', 1, 'view_permission'),
(5, 'Can add group', 2, 'add_group'),
(6, 'Can change group', 2, 'change_group'),
(7, 'Can delete group', 2, 'delete_group'),
(8, 'Can view group', 2, 'view_group'),
(9, 'Can add user', 3, 'add_user'),
(10, 'Can change user', 3, 'change_user'),
(11, 'Can delete user', 3, 'delete_user'),
(12, 'Can view user', 3, 'view_user'),
(13, 'Can add content type', 4, 'add_contenttype'),
(14, 'Can change content type', 4, 'change_contenttype'),
(15, 'Can delete content type', 4, 'delete_contenttype'),
(16, 'Can view content type', 4, 'view_contenttype'),
(17, 'Can add user', 5, 'add_user'),
(18, 'Can change user', 5, 'change_user'),
(19, 'Can delete user', 5, 'delete_user'),
(20, 'Can view user', 5, 'view_user'),
(21, 'Can add medicament', 6, 'add_medicament'),
(22, 'Can change medicament', 6, 'change_medicament'),
(23, 'Can delete medicament', 6, 'delete_medicament'),
(24, 'Can view medicament', 6, 'view_medicament'),
(25, 'Can add assignment', 7, 'add_assignment'),
(26, 'Can change assignment', 7, 'change_assignment'),
(27, 'Can delete assignment', 7, 'delete_assignment'),
(28, 'Can view assignment', 7, 'view_assignment'),
(29, 'Can add sim session', 8, 'add_simsession'),
(30, 'Can change sim session', 8, 'change_simsession'),
(31, 'Can delete sim session', 8, 'delete_simsession'),
(32, 'Can view sim session', 8, 'view_simsession'),
(33, 'Can add session memory', 9, 'add_sessionmemory'),
(34, 'Can change session memory', 9, 'change_sessionmemory'),
(35, 'Can delete session memory', 9, 'delete_sessionmemory'),
(36, 'Can view session memory', 9, 'view_sessionmemory');

-- --------------------------------------------------------

--
-- Structure de la table `auth_user`
--

CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_user_groups`
--

CREATE TABLE `auth_user_groups` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `auth_user_user_permissions`
--

CREATE TABLE `auth_user_user_permissions` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `django_content_type`
--

CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `django_content_type`
--

INSERT INTO `django_content_type` (`id`, `app_label`, `model`) VALUES
(7, 'api', 'assignment'),
(6, 'api', 'medicament'),
(9, 'api', 'sessionmemory'),
(8, 'api', 'simsession'),
(5, 'api', 'user'),
(2, 'auth', 'group'),
(1, 'auth', 'permission'),
(3, 'auth', 'user'),
(4, 'contenttypes', 'contenttype');

-- --------------------------------------------------------

--
-- Structure de la table `django_migrations`
--

CREATE TABLE `django_migrations` (
  `id` bigint(20) NOT NULL,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `django_migrations`
--

INSERT INTO `django_migrations` (`id`, `app`, `name`, `applied`) VALUES
(1, 'contenttypes', '0001_initial', '2026-05-05 10:03:27.675313'),
(2, 'contenttypes', '0002_remove_content_type_name', '2026-05-05 10:03:27.769898'),
(3, 'auth', '0001_initial', '2026-05-05 10:03:28.391305'),
(4, 'auth', '0002_alter_permission_name_max_length', '2026-05-05 10:03:28.477611'),
(5, 'auth', '0003_alter_user_email_max_length', '2026-05-05 10:03:28.501209'),
(6, 'auth', '0004_alter_user_username_opts', '2026-05-05 10:03:28.515832'),
(7, 'auth', '0005_alter_user_last_login_null', '2026-05-05 10:03:28.588909'),
(8, 'auth', '0006_require_contenttypes_0002', '2026-05-05 10:03:28.593910'),
(9, 'auth', '0007_alter_validators_add_error_messages', '2026-05-05 10:03:28.614360'),
(10, 'auth', '0008_alter_user_username_max_length', '2026-05-05 10:03:28.650172'),
(11, 'auth', '0009_alter_user_last_name_max_length', '2026-05-05 10:03:28.670191'),
(12, 'auth', '0010_alter_group_name_max_length', '2026-05-05 10:03:28.691028'),
(13, 'auth', '0011_update_proxy_permissions', '2026-05-05 10:03:28.714177'),
(14, 'auth', '0012_alter_user_first_name_max_length', '2026-05-05 10:03:28.747900');

-- --------------------------------------------------------

--
-- Structure de la table `medicaments`
--

CREATE TABLE `medicaments` (
  `id` int(11) NOT NULL,
  `nom` varchar(255) NOT NULL,
  `forme` varchar(100) DEFAULT NULL,
  `principe_actif` varchar(255) DEFAULT NULL,
  `classe_therapeutique` varchar(255) DEFAULT NULL,
  `indications` text DEFAULT NULL,
  `posologie` text DEFAULT NULL,
  `contre_indications` text DEFAULT NULL,
  `effets_indesirables` text DEFAULT NULL,
  `mecanisme_action` text DEFAULT NULL,
  `avantage_differentiant` text DEFAULT NULL,
  `conservation` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `medicaments`
--

INSERT INTO `medicaments` (`id`, `nom`, `forme`, `principe_actif`, `classe_therapeutique`, `indications`, `posologie`, `contre_indications`, `effets_indesirables`, `mecanisme_action`, `avantage_differentiant`, `conservation`, `created_at`) VALUES
(1, 'FONGIDERM Antifongique Crème', 'Crème topique 30g', 'Bifonazole 1%', 'Antifongique topique', 'Mycoses cutanées superficielles (pied d\'athlète, intertrigo, teigne, pityriasis versicolor)', '1 application par jour pendant 2 à 4 semaines', NULL, NULL, NULL, 'Une seule application quotidienne — observance optimale vs concurrents 2x/jour', NULL, '2026-05-05 09:56:58');

-- --------------------------------------------------------

--
-- Structure de la table `session_memory`
--

CREATE TABLE `session_memory` (
  `id` int(11) NOT NULL,
  `delegue_id` int(11) NOT NULL,
  `medicament_id` int(11) NOT NULL,
  `summary_text` text DEFAULT NULL,
  `weak_points` text DEFAULT NULL,
  `strong_points` text DEFAULT NULL,
  `last_module` int(11) NOT NULL DEFAULT 1,
  `session_date` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `sim_sessions`
--

CREATE TABLE `sim_sessions` (
  `id` int(11) NOT NULL,
  `delegue_id` int(11) NOT NULL,
  `medicament_id` int(11) NOT NULL,
  `mode` enum('training','exam') NOT NULL DEFAULT 'training',
  `interlocuteur` enum('medecin','pharmacien') NOT NULL DEFAULT 'medecin',
  `score_contenu` int(11) DEFAULT NULL,
  `score_comportement` int(11) DEFAULT NULL,
  `score_voix` int(11) DEFAULT NULL,
  `score_final` int(11) DEFAULT NULL,
  `nb_tours` int(11) NOT NULL DEFAULT 0,
  `duree_secondes` int(11) DEFAULT NULL,
  `bilan_text` text DEFAULT NULL,
  `conversation_json` longtext DEFAULT NULL,
  `vision_report_json` longtext DEFAULT NULL,
  `prosody_report_json` longtext DEFAULT NULL,
  `objets_detectes` varchar(500) DEFAULT NULL,
  `started_at` datetime NOT NULL DEFAULT current_timestamp(),
  `ended_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `role` enum('delegue','admin') NOT NULL DEFAULT 'delegue',
  `niveau` enum('debutant','intermediaire','avance') NOT NULL DEFAULT 'debutant',
  `current_module` int(11) NOT NULL DEFAULT 1,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `users`
--

INSERT INTO `users` (`id`, `email`, `password_hash`, `first_name`, `last_name`, `role`, `niveau`, `current_module`, `is_active`, `created_at`, `updated_at`) VALUES
(1, 'admin@alia.com', 'CHANGE_ME_HASH', 'Admin', 'Alia', 'admin', 'avance', 1, 1, '2026-05-05 09:56:58', '2026-05-05 09:56:58'),
(2, 'eya@alia.com', 'eya', 'Eya', 'Test', 'delegue', 'debutant', 1, 1, '2026-05-05 09:56:58', '2026-05-05 11:09:33');

--
-- Index pour les tables déchargées
--

--
-- Index pour la table `assignments`
--
ALTER TABLE `assignments`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_assignment` (`delegue_id`,`medicament_id`),
  ADD KEY `medicament_id` (`medicament_id`);

--
-- Index pour la table `auth_group`
--
ALTER TABLE `auth_group`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Index pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  ADD KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`);

--
-- Index pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`);

--
-- Index pour la table `auth_user`
--
ALTER TABLE `auth_user`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Index pour la table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  ADD KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`);

--
-- Index pour la table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  ADD KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`);

--
-- Index pour la table `django_content_type`
--
ALTER TABLE `django_content_type`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`);

--
-- Index pour la table `django_migrations`
--
ALTER TABLE `django_migrations`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `medicaments`
--
ALTER TABLE `medicaments`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nom` (`nom`);

--
-- Index pour la table `session_memory`
--
ALTER TABLE `session_memory`
  ADD PRIMARY KEY (`id`),
  ADD KEY `delegue_id` (`delegue_id`),
  ADD KEY `medicament_id` (`medicament_id`);

--
-- Index pour la table `sim_sessions`
--
ALTER TABLE `sim_sessions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `delegue_id` (`delegue_id`),
  ADD KEY `medicament_id` (`medicament_id`);

--
-- Index pour la table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`);

--
-- AUTO_INCREMENT pour les tables déchargées
--

--
-- AUTO_INCREMENT pour la table `assignments`
--
ALTER TABLE `assignments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT pour la table `auth_group`
--
ALTER TABLE `auth_group`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=37;

--
-- AUTO_INCREMENT pour la table `auth_user`
--
ALTER TABLE `auth_user`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `django_content_type`
--
ALTER TABLE `django_content_type`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT pour la table `django_migrations`
--
ALTER TABLE `django_migrations`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;

--
-- AUTO_INCREMENT pour la table `medicaments`
--
ALTER TABLE `medicaments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT pour la table `session_memory`
--
ALTER TABLE `session_memory`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `sim_sessions`
--
ALTER TABLE `sim_sessions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- Contraintes pour les tables déchargées
--

--
-- Contraintes pour la table `assignments`
--
ALTER TABLE `assignments`
  ADD CONSTRAINT `assignments_ibfk_1` FOREIGN KEY (`delegue_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `assignments_ibfk_2` FOREIGN KEY (`medicament_id`) REFERENCES `medicaments` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);

--
-- Contraintes pour la table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);

--
-- Contraintes pour la table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  ADD CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  ADD CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);

--
-- Contraintes pour la table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  ADD CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);

--
-- Contraintes pour la table `session_memory`
--
ALTER TABLE `session_memory`
  ADD CONSTRAINT `session_memory_ibfk_1` FOREIGN KEY (`delegue_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `session_memory_ibfk_2` FOREIGN KEY (`medicament_id`) REFERENCES `medicaments` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `sim_sessions`
--
ALTER TABLE `sim_sessions`
  ADD CONSTRAINT `sim_sessions_ibfk_1` FOREIGN KEY (`delegue_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `sim_sessions_ibfk_2` FOREIGN KEY (`medicament_id`) REFERENCES `medicaments` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
