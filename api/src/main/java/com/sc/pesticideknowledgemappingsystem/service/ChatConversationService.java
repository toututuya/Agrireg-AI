package com.sc.pesticideknowledgemappingsystem.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ChatConversationService {

    private static final int CONTEXT_MESSAGE_LIMIT = 4;
    private static final int CONTEXT_CONTENT_LIMIT = 1200;
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<List<String>>() {};
    private static final TypeReference<List<Map<String, Object>>> MAP_LIST =
            new TypeReference<List<Map<String, Object>>>() {};

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    public List<Map<String, Object>> list(String visitorId) {
        String sql = "SELECT c.id, c.title, c.created_at, c.updated_at, " +
                "(SELECT COUNT(*) FROM chat_message m WHERE m.conversation_id = c.id) " +
                "FROM chat_conversation c WHERE c.visitor_id = ? " +
                "ORDER BY c.updated_at DESC LIMIT 50";
        return jdbcTemplate.query(sql, new Object[]{normalizeVisitorId(visitorId)}, (row, index) -> {
            Map<String, Object> conversation = new LinkedHashMap<>();
            conversation.put("id", row.getString(1));
            conversation.put("title", row.getString(2));
            conversation.put("createdAt", iso(row.getTimestamp(3)));
            conversation.put("updatedAt", iso(row.getTimestamp(4)));
            conversation.put("messageCount", row.getLong(5));
            return conversation;
        });
    }

    public Map<String, Object> get(String visitorId, String conversationId) {
        Map<String, Object> conversation = requireConversation(normalizeVisitorId(visitorId), conversationId);
        String sql = "SELECT id, role, content, focus_entities, evidence, follow_ups, model, created_at " +
                "FROM chat_message WHERE conversation_id = ? ORDER BY id";
        List<Map<String, Object>> messages = jdbcTemplate.query(sql, new Object[]{conversationId}, (row, index) -> {
            Map<String, Object> message = new LinkedHashMap<>();
            message.put("id", row.getLong(1));
            message.put("role", row.getString(2));
            message.put("content", row.getString(3));
            message.put("focusEntities", readStringList(row.getString(4)));
            message.put("evidence", readMapList(row.getString(5)));
            message.put("followUps", readStringList(row.getString(6)));
            message.put("model", row.getString(7));
            message.put("createdAt", iso(row.getTimestamp(8)));
            return message;
        });
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversation", conversation);
        result.put("messages", messages);
        return result;
    }

    public List<Map<String, String>> recentContext(String visitorId, String conversationId) {
        if (!notBlank(conversationId)) return Collections.emptyList();
        requireConversation(normalizeVisitorId(visitorId), conversationId);
        String sql = "SELECT role, content FROM chat_message WHERE conversation_id = ? " +
                "ORDER BY id DESC LIMIT " + CONTEXT_MESSAGE_LIMIT;
        List<Map<String, String>> newestFirst = jdbcTemplate.query(sql, new Object[]{conversationId}, (row, index) -> {
            Map<String, String> message = new LinkedHashMap<>();
            message.put("role", row.getString(1));
            String content = row.getString(2);
            message.put("content", content.length() <= CONTEXT_CONTENT_LIMIT
                    ? content
                    : content.substring(0, CONTEXT_CONTENT_LIMIT));
            return message;
        });
        Collections.reverse(newestFirst);
        return newestFirst;
    }

    @Transactional
    public Map<String, Object> saveExchange(
            String visitorId,
            String conversationId,
            String question,
            Map<String, Object> assistantResult
    ) {
        String owner = normalizeVisitorId(visitorId);
        String id = conversationId;
        Timestamp now = Timestamp.from(Instant.now());
        if (!notBlank(id)) {
            id = UUID.randomUUID().toString();
            jdbcTemplate.update(
                    "INSERT INTO chat_conversation(id, visitor_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    id, owner, titleFrom(question), now, now
            );
        } else {
            requireConversation(owner, id);
        }

        jdbcTemplate.update(
                "INSERT INTO chat_message(conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                id, question, now
        );
        jdbcTemplate.update(
                "INSERT INTO chat_message(conversation_id, role, content, focus_entities, evidence, follow_ups, model, created_at) " +
                        "VALUES (?, 'assistant', ?, ?, ?, ?, ?, ?)",
                id,
                String.valueOf(assistantResult.get("answer")),
                json(assistantResult.get("focusEntities")),
                json(assistantResult.get("evidence")),
                json(assistantResult.get("followUps")),
                assistantResult.get("model") == null ? null : String.valueOf(assistantResult.get("model")),
                now
        );
        jdbcTemplate.update("UPDATE chat_conversation SET updated_at = ? WHERE id = ?", now, id);
        return requireConversation(owner, id);
    }

    @Transactional
    public boolean delete(String visitorId, String conversationId) {
        String owner = normalizeVisitorId(visitorId);
        int owned = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM chat_conversation WHERE id = ? AND visitor_id = ?",
                new Object[]{conversationId, owner},
                Integer.class
        );
        if (owned == 0) return false;
        return jdbcTemplate.update(
                "DELETE FROM chat_conversation WHERE id = ? AND visitor_id = ?",
                conversationId, owner
        ) > 0;
    }

    private Map<String, Object> requireConversation(String visitorId, String conversationId) {
        if (!notBlank(conversationId)) throw new IllegalArgumentException("conversation is required");
        List<Map<String, Object>> rows = jdbcTemplate.query(
                "SELECT id, title, created_at, updated_at FROM chat_conversation WHERE id = ? AND visitor_id = ?",
                new Object[]{conversationId, visitorId},
                (row, index) -> {
                    Map<String, Object> conversation = new LinkedHashMap<>();
                    conversation.put("id", row.getString(1));
                    conversation.put("title", row.getString(2));
                    conversation.put("createdAt", iso(row.getTimestamp(3)));
                    conversation.put("updatedAt", iso(row.getTimestamp(4)));
                    return conversation;
                }
        );
        if (rows.isEmpty()) throw new IllegalArgumentException("conversation not found");
        return rows.get(0);
    }

    private String normalizeVisitorId(String visitorId) {
        String value = notBlank(visitorId) ? visitorId.trim() : "local-demo";
        if (value.length() > 80) throw new IllegalArgumentException("visitor id is too long");
        return value;
    }

    private String titleFrom(String question) {
        String value = question.replaceAll("\\s+", " ").trim();
        return value.length() <= 30 ? value : value.substring(0, 30) + "…";
    }

    private String json(Object value) {
        try {
            return objectMapper.writeValueAsString(value == null ? Collections.emptyList() : value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("cannot serialize conversation message", exception);
        }
    }

    private List<String> readStringList(String value) {
        if (!notBlank(value)) return Collections.emptyList();
        try {
            return objectMapper.readValue(value, STRING_LIST);
        } catch (JsonProcessingException exception) {
            return Collections.emptyList();
        }
    }

    private List<Map<String, Object>> readMapList(String value) {
        if (!notBlank(value)) return Collections.emptyList();
        try {
            return objectMapper.readValue(value, MAP_LIST);
        } catch (JsonProcessingException exception) {
            return new ArrayList<>();
        }
    }

    private String iso(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant().toString();
    }

    private boolean notBlank(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
