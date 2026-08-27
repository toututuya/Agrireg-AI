CREATE TABLE IF NOT EXISTS chat_conversation (
    id VARCHAR(36) PRIMARY KEY,
    visitor_id VARCHAR(80) NOT NULL,
    title VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_conversation_visitor_updated
    ON chat_conversation(visitor_id, updated_at);

CREATE TABLE IF NOT EXISTS chat_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content CLOB NOT NULL,
    focus_entities CLOB,
    evidence CLOB,
    follow_ups CLOB,
    model VARCHAR(80),
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT fk_chat_message_conversation
        FOREIGN KEY (conversation_id) REFERENCES chat_conversation(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_message_conversation_id
    ON chat_message(conversation_id, id);
