-- ==========================================================
-- TicketGenie Database Schema
-- Step 1: Roles Table
-- ==========================================================

CREATE TABLE dbo.Roles (

    role_id INT IDENTITY(1,1) PRIMARY KEY,

    role_name NVARCHAR(50) NOT NULL UNIQUE,

    description NVARCHAR(255),

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME()

);
GO

-- ==========================================================
-- Step 2: Users Table
-- ==========================================================

CREATE TABLE dbo.Users (

    user_id INT IDENTITY(1,1) PRIMARY KEY,

    username NVARCHAR(100) NOT NULL UNIQUE,

    email NVARCHAR(255) NOT NULL UNIQUE,

    password_hash NVARCHAR(255) NOT NULL,

    first_name NVARCHAR(100) NOT NULL,

    last_name NVARCHAR(100) NOT NULL,

    role_id INT NOT NULL,

    department NVARCHAR(10) NULL,

    is_active BIT NOT NULL
        DEFAULT 1,

    failed_login_attempts INT NOT NULL
        DEFAULT 0,

    account_locked_until DATETIME2 NULL,

    last_login_at DATETIME2 NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    updated_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_Users_Roles
        FOREIGN KEY (role_id)
        REFERENCES dbo.Roles(role_id),

    CONSTRAINT CK_Users_Department
        CHECK (
            department IS NULL
            OR department IN ('HR', 'IT')
        )
);
GO

-- ==========================================================
-- Step 3: Tickets Table
-- ==========================================================

CREATE TABLE dbo.Tickets (

    ticket_id INT IDENTITY(1,1) PRIMARY KEY,

    ticket_number NVARCHAR(30) NOT NULL UNIQUE,

    created_by_user_id INT NOT NULL,

    assigned_to_user_id INT NULL,

    department NVARCHAR(10) NOT NULL,

    category NVARCHAR(100) NULL,

    title NVARCHAR(200) NOT NULL,

    description NVARCHAR(MAX) NOT NULL,

    status NVARCHAR(30) NOT NULL
        DEFAULT 'OPEN',

    priority NVARCHAR(10) NOT NULL
        DEFAULT 'P3',

    is_anonymous BIT NOT NULL
        DEFAULT 0,

    ai_summary NVARCHAR(MAX) NULL,

    ai_suggested_response NVARCHAR(MAX) NULL,

    ai_priority_confidence DECIMAL(5,4) NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    updated_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    resolved_at DATETIME2 NULL,

    closed_at DATETIME2 NULL,

    CONSTRAINT FK_Tickets_CreatedBy
        FOREIGN KEY (created_by_user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT FK_Tickets_AssignedTo
        FOREIGN KEY (assigned_to_user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT CK_Tickets_Department
        CHECK (department IN ('HR', 'IT')),

    CONSTRAINT CK_Tickets_Status
        CHECK (
            status IN (
                'OPEN',
                'IN_PROGRESS',
                'WAITING_FOR_EMPLOYEE',
                'RESOLVED',
                'CLOSED'
            )
        ),

    CONSTRAINT CK_Tickets_Priority
        CHECK (
            priority IN ('P1', 'P2', 'P3', 'P4', 'P5')
        ),

    CONSTRAINT CK_Tickets_AIConfidence
        CHECK (
            ai_priority_confidence IS NULL
            OR ai_priority_confidence BETWEEN 0 AND 1
        )
);
GO

-- ==========================================================
-- Step 4: TicketMessages Table
-- ==========================================================

CREATE TABLE dbo.TicketMessages (

    message_id INT IDENTITY(1,1) PRIMARY KEY,

    ticket_id INT NOT NULL,

    sender_user_id INT NULL,

    sender_type NVARCHAR(20) NOT NULL,

    message_text NVARCHAR(MAX) NOT NULL,

    is_ai_generated BIT NOT NULL
        DEFAULT 0,

    is_internal_note BIT NOT NULL
        DEFAULT 0,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    edited_at DATETIME2 NULL,

    CONSTRAINT FK_TicketMessages_Tickets
        FOREIGN KEY (ticket_id)
        REFERENCES dbo.Tickets(ticket_id),

    CONSTRAINT FK_TicketMessages_Users
        FOREIGN KEY (sender_user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT CK_TicketMessages_SenderType
        CHECK (
            sender_type IN (
                'EMPLOYEE',
                'TICKETER',
                'AI',
                'SYSTEM'
            )
        )
);
GO

-- ==========================================================
-- Step 5: Ticket History
-- ==========================================================

CREATE TABLE dbo.TicketHistory (

    history_id INT IDENTITY(1,1) PRIMARY KEY,

    ticket_id INT NOT NULL,

    changed_by_user_id INT NULL,

    action_type NVARCHAR(50) NOT NULL,

    old_value NVARCHAR(255) NULL,

    new_value NVARCHAR(255) NULL,

    change_reason NVARCHAR(500) NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_TicketHistory_Ticket
        FOREIGN KEY (ticket_id)
        REFERENCES dbo.Tickets(ticket_id),

    CONSTRAINT FK_TicketHistory_User
        FOREIGN KEY (changed_by_user_id)
        REFERENCES dbo.Users(user_id)

);
GO

-- ==========================================================
-- Step 6: Knowledge Documents
-- ==========================================================

CREATE TABLE dbo.KnowledgeDocuments (

    document_id INT IDENTITY(1,1) PRIMARY KEY,

    title NVARCHAR(255) NOT NULL,

    department NVARCHAR(10) NOT NULL,

    document_type NVARCHAR(50) NULL,

    blob_path NVARCHAR(500) NOT NULL,

    document_version NVARCHAR(50) NULL,

    uploaded_by_user_id INT NOT NULL,

    is_active BIT NOT NULL
        DEFAULT 1,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    updated_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_KnowledgeDocuments_UploadedBy
        FOREIGN KEY (uploaded_by_user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT CK_KnowledgeDocuments_Department
        CHECK (
            department IN ('HR', 'IT')
        )
);
GO

-- ==========================================================
-- Step 7: Chat Sessions
-- ==========================================================

CREATE TABLE dbo.ChatSessions (

    session_id INT IDENTITY(1,1) PRIMARY KEY,

    user_id INT NOT NULL,

    department NVARCHAR(10) NOT NULL,

    session_title NVARCHAR(200) NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    updated_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_ChatSessions_User
        FOREIGN KEY (user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT CK_ChatSessions_Department
        CHECK (
            department IN ('HR', 'IT')
        )
);
GO

-- ==========================================================
-- Step 8: Chat Messages
-- ==========================================================

CREATE TABLE dbo.ChatMessages (

    chat_message_id INT IDENTITY(1,1) PRIMARY KEY,

    session_id INT NOT NULL,

    sender_type NVARCHAR(10) NOT NULL,

    message_text NVARCHAR(MAX) NOT NULL,

    source_references NVARCHAR(MAX) NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_ChatMessages_Session
        FOREIGN KEY (session_id)
        REFERENCES dbo.ChatSessions(session_id),

    CONSTRAINT CK_ChatMessages_SenderType
        CHECK (
            sender_type IN ('USER', 'AI')
        )
);
GO

-- ==========================================================
-- Step 9: Attachments
-- ==========================================================

CREATE TABLE dbo.Attachments (

    attachment_id INT IDENTITY(1,1) PRIMARY KEY,

    ticket_id INT NOT NULL,

    uploaded_by_user_id INT NOT NULL,

    file_name NVARCHAR(255) NOT NULL,

    blob_path NVARCHAR(500) NOT NULL,

    content_type NVARCHAR(100) NULL,

    file_size_bytes BIGINT NULL,

    uploaded_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_Attachments_Ticket
        FOREIGN KEY (ticket_id)
        REFERENCES dbo.Tickets(ticket_id),

    CONSTRAINT FK_Attachments_User
        FOREIGN KEY (uploaded_by_user_id)
        REFERENCES dbo.Users(user_id)
);
GO

-- ==========================================================
-- Step 10: AI Interactions
-- ==========================================================

CREATE TABLE dbo.AIInteractions (

    interaction_id INT IDENTITY(1,1) PRIMARY KEY,

    ticket_id INT NULL,

    chat_session_id INT NULL,

    interaction_type NVARCHAR(50) NOT NULL,

    model_name NVARCHAR(100) NULL,

    input_text NVARCHAR(MAX) NULL,

    output_text NVARCHAR(MAX) NOT NULL,

    confidence_score DECIMAL(5,4) NULL,

    was_accepted BIT NULL,

    reviewed_by_user_id INT NULL,

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_AIInteractions_Ticket
        FOREIGN KEY (ticket_id)
        REFERENCES dbo.Tickets(ticket_id),

    CONSTRAINT FK_AIInteractions_ChatSession
        FOREIGN KEY (chat_session_id)
        REFERENCES dbo.ChatSessions(session_id),

    CONSTRAINT FK_AIInteractions_ReviewedBy
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES dbo.Users(user_id),

    CONSTRAINT CK_AIInteractions_Type
        CHECK (
            interaction_type IN (
                'PRIORITY_CLASSIFICATION',
                'TICKET_SUMMARY',
                'SUGGESTED_RESPONSE',
                'TICKET_ROUTING',
                'CHATBOT_RESPONSE'
            )
        ),

    CONSTRAINT CK_AIInteractions_Confidence
        CHECK (
            confidence_score IS NULL
            OR confidence_score BETWEEN 0 AND 1
        ),

    CONSTRAINT CK_AIInteractions_Context
        CHECK (
            ticket_id IS NOT NULL
            OR chat_session_id IS NOT NULL
        )
);
GO