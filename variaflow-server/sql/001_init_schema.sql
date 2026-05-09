-- VariaFlow MVP 阶段数据库结构
-- 目标数据库：MySQL 8.0+
-- 说明：所有 DATETIME 值统一由应用层按 UTC 写入。

CREATE DATABASE IF NOT EXISTS `variaflow`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `variaflow`;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `batch_job` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `batch_code` VARCHAR(64) NOT NULL COMMENT '由应用层生成的唯一批次编码',
  `status` ENUM(
    'pending',
    'ingesting',
    'ready',
    'running',
    'partial_success',
    'completed',
    'failed',
    'cancelled'
  ) NOT NULL DEFAULT 'pending',
  `upload_mode` ENUM('zip', 'folder') NOT NULL,
  `original_upload_name` VARCHAR(255) NULL,
  `input_archive_path` VARCHAR(1024) NULL,
  `input_root_path` VARCHAR(1024) NULL,
  `unzip_root_path` VARCHAR(1024) NULL,
  `normalized_root_path` VARCHAR(1024) NULL,
  `output_root_path` VARCHAR(1024) NULL,
  `failed_root_path` VARCHAR(1024) NULL,
  `export_zip_path` VARCHAR(1024) NULL,
  `export_status` ENUM('not_requested', 'queued', 'processing', 'success', 'failed') NOT NULL DEFAULT 'not_requested',
  `target_variant_count` TINYINT UNSIGNED NOT NULL DEFAULT 3,
  `total_source_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `total_generation_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `completed_source_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `partial_source_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `failed_source_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `success_generation_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `failed_generation_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `scheduler_started_at` DATETIME(3) NULL,
  `scheduler_finished_at` DATETIME(3) NULL,
  `exported_at` DATETIME(3) NULL,
  `last_error_code` VARCHAR(64) NULL,
  `last_error_message` VARCHAR(1024) NULL,
  `created_by` VARCHAR(128) NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_job_batch_code` (`batch_code`),
  KEY `idx_batch_job_status_created_at` (`status`, `created_at`),
  KEY `idx_batch_job_export_status` (`export_status`, `updated_at`),
  CONSTRAINT `chk_batch_job_target_variant_count`
    CHECK (`target_variant_count` BETWEEN 2 AND 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `prompt_profile` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `profile_code` VARCHAR(64) NOT NULL,
  `profile_name` VARCHAR(128) NOT NULL,
  `subject_category` VARCHAR(64) NULL,
  `positive_template` MEDIUMTEXT NOT NULL,
  `negative_template` MEDIUMTEXT NOT NULL,
  `identity_template` MEDIUMTEXT NULL,
  `quality_template` MEDIUMTEXT NULL,
  `is_default` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prompt_profile_code` (`profile_code`),
  KEY `idx_prompt_profile_active` (`is_active`, `is_default`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `prompt_variable_option` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `prompt_profile_id` BIGINT UNSIGNED NOT NULL,
  `variable_type` ENUM('action', 'outfit', 'scene', 'camera', 'style') NOT NULL,
  `option_key` VARCHAR(64) NOT NULL,
  `option_label` VARCHAR(128) NOT NULL,
  `prompt_fragment` VARCHAR(512) NOT NULL,
  `sort_order` INT UNSIGNED NOT NULL DEFAULT 0,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prompt_variable_option` (`prompt_profile_id`, `variable_type`, `option_key`),
  KEY `idx_prompt_variable_option_enabled` (`prompt_profile_id`, `variable_type`, `is_enabled`, `sort_order`),
  CONSTRAINT `fk_prompt_variable_option_profile`
    FOREIGN KEY (`prompt_profile_id`) REFERENCES `prompt_profile` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `batch_prompt_config` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `batch_id` BIGINT UNSIGNED NOT NULL,
  `prompt_profile_id` BIGINT UNSIGNED NULL,
  `variant_generation_mode` ENUM('matrix', 'manual') NOT NULL DEFAULT 'matrix',
  `positive_override` MEDIUMTEXT NULL,
  `negative_override` MEDIUMTEXT NULL,
  `identity_lock_override` MEDIUMTEXT NULL,
  `quality_override` MEDIUMTEXT NULL,
  `selected_actions_json` JSON NULL,
  `selected_outfits_json` JSON NULL,
  `selected_scenes_json` JSON NULL,
  `selected_cameras_json` JSON NULL,
  `selected_styles_json` JSON NULL,
  `custom_variables_json` JSON NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_prompt_config_batch_id` (`batch_id`),
  KEY `idx_batch_prompt_config_profile` (`prompt_profile_id`),
  CONSTRAINT `fk_batch_prompt_config_batch`
    FOREIGN KEY (`batch_id`) REFERENCES `batch_job` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_batch_prompt_config_profile`
    FOREIGN KEY (`prompt_profile_id`) REFERENCES `prompt_profile` (`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `source_task` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `batch_id` BIGINT UNSIGNED NOT NULL,
  `source_index` INT UNSIGNED NOT NULL,
  `status` ENUM('pending', 'partial_success', 'completed', 'failed') NOT NULL DEFAULT 'pending',
  `source_name` VARCHAR(255) NOT NULL,
  `source_ext` VARCHAR(16) NOT NULL,
  `source_relative_path` VARCHAR(1024) NULL,
  `source_path` VARCHAR(1024) NOT NULL,
  `normalized_path` VARCHAR(1024) NULL,
  `source_hash` CHAR(64) NOT NULL,
  `source_size_bytes` BIGINT UNSIGNED NOT NULL,
  `source_width` INT UNSIGNED NULL,
  `source_height` INT UNSIGNED NULL,
  `target_variant_count` TINYINT UNSIGNED NOT NULL,
  `success_count` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `failed_count` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `identity_profile_json` JSON NULL,
  `last_error_code` VARCHAR(64) NULL,
  `last_error_message` VARCHAR(1024) NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_source_task_batch_source_index` (`batch_id`, `source_index`),
  KEY `idx_source_task_batch_status` (`batch_id`, `status`, `source_index`),
  KEY `idx_source_task_hash` (`source_hash`),
  CONSTRAINT `fk_source_task_batch`
    FOREIGN KEY (`batch_id`) REFERENCES `batch_job` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `chk_source_task_target_variant_count`
    CHECK (`target_variant_count` BETWEEN 2 AND 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `generation_task` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `batch_id` BIGINT UNSIGNED NOT NULL,
  `source_task_id` BIGINT UNSIGNED NOT NULL,
  `variant_index` TINYINT UNSIGNED NOT NULL,
  `variant_axis` ENUM('action', 'outfit', 'scene', 'mixed') NOT NULL DEFAULT 'mixed',
  `status` ENUM('pending', 'processing', 'success', 'failed', 'fallback_success', 'retrying') NOT NULL DEFAULT 'pending',
  `variant_plan_json` JSON NULL,
  `prompt_snapshot_json` JSON NULL,
  `provider_final` VARCHAR(32) NULL COMMENT '最终使用的供应商编码，例如 openai_image_2 或 aliyun_wanx',
  `provider_route_final` ENUM('primary', 'fallback') NULL,
  `attempt_count` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `max_attempts` SMALLINT UNSIGNED NOT NULL DEFAULT 3,
  `next_run_at` DATETIME(3) NULL,
  `lease_owner` VARCHAR(128) NULL,
  `lease_until` DATETIME(3) NULL,
  `processing_started_at` DATETIME(3) NULL,
  `completed_at` DATETIME(3) NULL,
  `output_file_name` VARCHAR(255) NULL,
  `output_ext` VARCHAR(16) NULL,
  `output_path` VARCHAR(1024) NULL,
  `output_hash` CHAR(64) NULL,
  `output_size_bytes` BIGINT UNSIGNED NULL,
  `output_width` INT UNSIGNED NULL,
  `output_height` INT UNSIGNED NULL,
  `qc_status` ENUM('pending', 'passed', 'failed', 'skipped') NOT NULL DEFAULT 'pending',
  `qc_fail_codes_json` JSON NULL,
  `last_error_code` VARCHAR(64) NULL,
  `last_error_message` VARCHAR(1024) NULL,
  `last_provider_http_status` SMALLINT UNSIGNED NULL,
  `last_switch_reason` VARCHAR(64) NULL,
  `manual_retry_requested` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_generation_task_source_variant` (`source_task_id`, `variant_index`),
  KEY `idx_generation_task_scheduler` (`status`, `next_run_at`, `lease_until`, `id`),
  KEY `idx_generation_task_batch_status` (`batch_id`, `status`, `id`),
  KEY `idx_generation_task_source_status` (`source_task_id`, `status`, `id`),
  KEY `idx_generation_task_manual_retry` (`manual_retry_requested`, `status`, `next_run_at`),
  KEY `idx_generation_task_output_hash` (`output_hash`),
  CONSTRAINT `fk_generation_task_batch`
    FOREIGN KEY (`batch_id`) REFERENCES `batch_job` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_generation_task_source`
    FOREIGN KEY (`source_task_id`) REFERENCES `source_task` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `chk_generation_task_variant_index`
    CHECK (`variant_index` BETWEEN 1 AND 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `generation_attempt` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `generation_task_id` BIGINT UNSIGNED NOT NULL,
  `attempt_no` SMALLINT UNSIGNED NOT NULL,
  `provider_route` ENUM('primary', 'fallback') NOT NULL,
  `provider_code` VARCHAR(32) NOT NULL,
  `provider_request_id` VARCHAR(128) NULL,
  `request_payload_hash` CHAR(64) NULL,
  `request_payload_json` JSON NULL,
  `response_meta_json` JSON NULL,
  `http_status` SMALLINT UNSIGNED NULL,
  `started_at` DATETIME(3) NOT NULL,
  `finished_at` DATETIME(3) NULL,
  `latency_ms` INT UNSIGNED NULL,
  `switch_reason` VARCHAR(64) NULL,
  `outcome` ENUM('started', 'success', 'retryable_error', 'fatal_error', 'timeout', 'qc_failed') NOT NULL,
  `error_code` VARCHAR(64) NULL,
  `error_message` VARCHAR(2048) NULL,
  `temporary_file_path` VARCHAR(1024) NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_generation_attempt_task_attempt_no` (`generation_task_id`, `attempt_no`),
  KEY `idx_generation_attempt_provider` (`provider_code`, `started_at`),
  KEY `idx_generation_attempt_outcome` (`outcome`, `started_at`),
  CONSTRAINT `fk_generation_attempt_task`
    FOREIGN KEY (`generation_task_id`) REFERENCES `generation_task` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `quality_check_result` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `generation_task_id` BIGINT UNSIGNED NOT NULL,
  `generation_attempt_id` BIGINT UNSIGNED NOT NULL,
  `qc_mode` ENUM('rules_only', 'hybrid') NOT NULL DEFAULT 'rules_only',
  `verdict` ENUM('passed', 'failed') NOT NULL,
  `rules_passed` TINYINT(1) NOT NULL DEFAULT 0,
  `model_passed` TINYINT(1) NULL,
  `min_file_size_ok` TINYINT(1) NOT NULL DEFAULT 0,
  `resolution_ok` TINYINT(1) NOT NULL DEFAULT 0,
  `mime_type_ok` TINYINT(1) NOT NULL DEFAULT 0,
  `sharpness_score` DECIMAL(8,4) NULL,
  `watermark_score` DECIMAL(8,4) NULL,
  `anatomy_score` DECIMAL(8,4) NULL,
  `identity_similarity` DECIMAL(8,4) NULL,
  `duplicate_similarity` DECIMAL(8,4) NULL,
  `fail_codes_json` JSON NULL,
  `metrics_json` JSON NULL,
  `checked_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_quality_check_result_attempt` (`generation_attempt_id`),
  KEY `idx_quality_check_result_task_verdict` (`generation_task_id`, `verdict`, `checked_at`),
  CONSTRAINT `fk_quality_check_result_task`
    FOREIGN KEY (`generation_task_id`) REFERENCES `generation_task` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_quality_check_result_attempt`
    FOREIGN KEY (`generation_attempt_id`) REFERENCES `generation_attempt` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `task_event_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `batch_id` BIGINT UNSIGNED NULL,
  `source_task_id` BIGINT UNSIGNED NULL,
  `generation_task_id` BIGINT UNSIGNED NULL,
  `event_type` VARCHAR(64) NOT NULL,
  `prev_status` VARCHAR(32) NULL,
  `next_status` VARCHAR(32) NULL,
  `actor_type` ENUM('system', 'scheduler', 'user') NOT NULL DEFAULT 'system',
  `actor_id` VARCHAR(128) NULL,
  `event_message` VARCHAR(1024) NULL,
  `payload_json` JSON NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_task_event_log_batch_time` (`batch_id`, `created_at`),
  KEY `idx_task_event_log_source_time` (`source_task_id`, `created_at`),
  KEY `idx_task_event_log_generation_time` (`generation_task_id`, `created_at`),
  KEY `idx_task_event_log_event_type_time` (`event_type`, `created_at`),
  CONSTRAINT `fk_task_event_log_batch`
    FOREIGN KEY (`batch_id`) REFERENCES `batch_job` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_task_event_log_source`
    FOREIGN KEY (`source_task_id`) REFERENCES `source_task` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_task_event_log_generation`
    FOREIGN KEY (`generation_task_id`) REFERENCES `generation_task` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `system_runtime_config` (
  `config_key` VARCHAR(64) NOT NULL,
  `config_value_type` ENUM('int', 'bool', 'string', 'float', 'json') NOT NULL,
  `config_payload` JSON NOT NULL,
  `description` VARCHAR(255) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`config_key`),
  KEY `idx_system_runtime_config_active` (`is_active`, `config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `system_runtime_config` (`config_key`, `config_value_type`, `config_payload`, `description`)
VALUES
  ('max_concurrency', 'int', JSON_OBJECT('value', 1), '最大并发生成任务数。MVP 严格串行时保持为 1。'),
  ('provider_request_timeout_ms', 'int', JSON_OBJECT('value', 90000), '单次供应商请求超时时间，单位毫秒。'),
  ('task_attempt_budget_ms', 'int', JSON_OBJECT('value', 120000), '单个生成槽位的总执行预算，包含兜底切换。'),
  ('provider_rate_limit_per_minute', 'int', JSON_OBJECT('value', 12), '调度器令牌桶使用的软性每分钟限流值。'),
  ('generation_max_attempts', 'int', JSON_OBJECT('value', 3), '单个生成任务允许的最大尝试次数。'),
  ('retry_backoff_schedule', 'json', JSON_ARRAY(5, 20, 60), '可重试失败的退避延迟计划，单位秒。'),
  ('qc_mode', 'string', JSON_OBJECT('value', 'rules_only'), 'MVP 质检模式，V2 可升级为 hybrid。'),
  ('qc_min_file_size_bytes', 'int', JSON_OBJECT('value', 51200), '规则质检允许的最小输出文件大小。'),
  ('qc_min_width', 'int', JSON_OBJECT('value', 1024), '规则质检允许的最小输出宽度。'),
  ('qc_min_height', 'int', JSON_OBJECT('value', 1024), '规则质检允许的最小输出高度。')
ON DUPLICATE KEY UPDATE
  `config_value_type` = VALUES(`config_value_type`),
  `config_payload` = VALUES(`config_payload`),
  `description` = VALUES(`description`),
  `is_active` = 1,
  `updated_at` = CURRENT_TIMESTAMP(3);

INSERT INTO `prompt_profile` (
  `profile_code`,
  `profile_name`,
  `subject_category`,
  `positive_template`,
  `negative_template`,
  `identity_template`,
  `quality_template`,
  `is_default`,
  `is_active`
)
VALUES (
  'default_ecommerce_identity',
  '默认电商主体锁定配置',
  'general',
  'Keep the subject identity consistent with the reference image. {{identity_lock}}. Apply the requested variation: {{variant_directive}}.',
  'no extra limbs, no extra fingers, no blur, no watermark, no text overlay, no deformed face, no duplicated subject, no cropped product, no low-resolution output',
  'Preserve the exact subject species, facial features, color palette, material texture, signature accessories, and product silhouette from the reference image',
  'high detail, clean commercial composition, complete subject, sharp focus, marketplace-ready hero image',
  1,
  1
)
ON DUPLICATE KEY UPDATE
  `profile_name` = VALUES(`profile_name`),
  `subject_category` = VALUES(`subject_category`),
  `positive_template` = VALUES(`positive_template`),
  `negative_template` = VALUES(`negative_template`),
  `identity_template` = VALUES(`identity_template`),
  `quality_template` = VALUES(`quality_template`),
  `is_default` = VALUES(`is_default`),
  `is_active` = VALUES(`is_active`),
  `updated_at` = CURRENT_TIMESTAMP(3);
