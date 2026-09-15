ALTER TABLE `auth_invite_tokens`
  ADD COLUMN `used_by` INT NULL AFTER `used_at`,
  ADD KEY `idx_auth_invite_tokens_used_by` (`used_by`),
  ADD CONSTRAINT `fk_auth_invite_tokens_used_by`
    FOREIGN KEY (`used_by`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE;
