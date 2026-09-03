-- ==========================================================
-- TicketGenie Database Indexes
-- ==========================================================

CREATE INDEX IX_Users_RoleId
ON dbo.Users(role_id);
GO

CREATE INDEX IX_Users_Department
ON dbo.Users(department);
GO

CREATE INDEX IX_Tickets_CreatedByUserId
ON dbo.Tickets(created_by_user_id);
GO

CREATE INDEX IX_Tickets_AssignedToUserId
ON dbo.Tickets(assigned_to_user_id);
GO

CREATE INDEX IX_Tickets_Department_Status
ON dbo.Tickets(department, status);
GO

CREATE INDEX IX_Tickets_Priority
ON dbo.Tickets(priority);
GO

CREATE INDEX IX_Tickets_CreatedAt
ON dbo.Tickets(created_at);
GO

CREATE INDEX IX_TicketMessages_TicketId_CreatedAt
ON dbo.TicketMessages(ticket_id, created_at);
GO

CREATE INDEX IX_TicketHistory_TicketId_CreatedAt
ON dbo.TicketHistory(ticket_id, created_at);
GO

CREATE INDEX IX_KnowledgeDocuments_Department_Active
ON dbo.KnowledgeDocuments(department, is_active);
GO

CREATE INDEX IX_ChatSessions_UserId_UpdatedAt
ON dbo.ChatSessions(user_id, updated_at);
GO

CREATE INDEX IX_ChatMessages_SessionId_CreatedAt
ON dbo.ChatMessages(session_id, created_at);
GO

CREATE INDEX IX_Attachments_TicketId
ON dbo.Attachments(ticket_id);
GO

CREATE INDEX IX_AIInteractions_TicketId_CreatedAt
ON dbo.AIInteractions(ticket_id, created_at);
GO

CREATE INDEX IX_AIInteractions_ChatSessionId_CreatedAt
ON dbo.AIInteractions(chat_session_id, created_at);
GO

CREATE INDEX IX_AIInteractions_Type_CreatedAt
ON dbo.AIInteractions(interaction_type, created_at);
GO