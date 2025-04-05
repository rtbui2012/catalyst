/**
 * Catalyst AI Web UI - Chat JavaScript
 * This file handles the chat interface functionality using a modular approach
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the chat application
    const chatApp = new CatalystChat();
    chatApp.initialize();
    
    // Make the chat app instance available globally for the displayEvent function
    window.chatAppInstance = chatApp;
});


/**
 * CatalystChat - Main application class
 * Handles the chat interface and conversation management
 */
class CatalystChat {
    constructor() {
        // DOM elements
        this.elements = {
            chatInput: document.getElementById('chat-input'),
            sendButton: document.getElementById('send-message'),
            chatMessages: document.getElementById('chat-messages'),
            clearChatButton: document.getElementById('clear-chat'),
            exportChatButton: document.getElementById('export-chat'),
            newChatButton: document.getElementById('new-chat'),
            conversationList: document.getElementById('conversation-list'),
            eventsContainer: null // Will be created dynamically when needed
        };
        
        // Chat state
        this.state = {
            isProcessing: false,
            messageHistory: [],
            currentConversationId: null,
            currentTitle: null,
            currentIcon: null,
            isEditing: false,
            currentEditId: null,
            savedConversations: [],
            eventSource: null,
            events: [], // Store events for the current message
            thinkingMessageId: null
        };
    }
    
    /**
     * Initialize the chat application
     */
    initialize() {
        // Load saved conversations from local storage
        this.loadSavedConversations();
        
        // Create or load a conversation
        if (!this.state.currentConversationId) {
            this.startNewChat(false);
        } else {
            this.loadConversation(this.state.currentConversationId);
        }
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Auto-resize textarea as user types
        this.autoResizeTextarea(this.elements.chatInput);
    }
    
    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Input and message sending
        this.elements.chatInput.addEventListener('input', this.handleInput.bind(this));
        this.elements.chatInput.addEventListener('keydown', this.handleKeyDown.bind(this));
        this.elements.sendButton.addEventListener('click', this.sendMessage.bind(this));
        
        // Button actions
        this.elements.clearChatButton.addEventListener('click', this.clearChat.bind(this));
        this.elements.exportChatButton.addEventListener('click', this.exportChat.bind(this));
        this.elements.newChatButton.addEventListener('click', () => this.startNewChat(true));
        
        // Handle click outside when editing
        document.addEventListener('click', (event) => {
            if (!this.state.isEditing) return;
            
            const editingMessage = document.querySelector('.message.editing');
            if (!editingMessage) return;
            
            // Check if the click was outside the editing message bubble
            if (!editingMessage.contains(event.target)) {
                const originalContent = this.state.messageHistory.find(
                    msg => msg.id === this.state.currentEditId
                )?.content;
                
                if (originalContent !== undefined) {
                    this.cancelEdit(editingMessage, originalContent);
                }
            }
        });
    }
    
    /**
     * Load saved conversations from local storage
     */
    loadSavedConversations() {
        try {
            const savedConvsJson = localStorage.getItem('catalyst_conversations');
            if (savedConvsJson) {
                this.state.savedConversations = JSON.parse(savedConvsJson);
                
                // Load last active conversation ID
                this.state.currentConversationId = localStorage.getItem('catalyst_current_conversation');
                
                // Populate conversation list in sidebar
                this.renderConversationList();
            }
        } catch (error) {
            console.error('Error loading saved conversations:', error);
            this.state.savedConversations = [];
        }
    }
    
    /**
     * Save conversations to local storage
     */
    saveConversationsToLocalStorage() {
        try {
            localStorage.setItem('catalyst_conversations', JSON.stringify(this.state.savedConversations));
            localStorage.setItem('catalyst_current_conversation', this.state.currentConversationId);
        } catch (error) {
            console.error('Error saving conversations to local storage:', error);
        }
    }
    
    /**
     * Render the conversation list in the sidebar
     */
    renderConversationList() {
        // Clear the list first
        this.elements.conversationList.innerHTML = '';

        if (this.state.savedConversations.length === 0) {
            this.elements.conversationList.innerHTML = '<div class="empty-state"><p>No conversations yet</p></div>';
            return;
        }

        // Sort conversations by last updated date (newest first)
        const sortedConversations = [...this.state.savedConversations].sort((a, b) =>
            new Date(b.updatedAt) - new Date(a.updatedAt)
        );

        // Add each conversation to the list
        sortedConversations.forEach(conversation => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('conversation-item');
            if (conversation.id === this.state.currentConversationId) {
                itemDiv.classList.add('active');
            }
            itemDiv.dataset.id = conversation.id;

            // Extract the icon from the title if it exists
            let displayTitle = conversation.title;
            let iconHtml = '';

            if (conversation.icon) {
                iconHtml = `<span class="conversation-icon">${conversation.icon}</span>`;
            } else {
                const emojiMatch = conversation.title.match(/^(\p{Emoji})/u);
                if (emojiMatch) {
                    iconHtml = `<span class="conversation-icon">${emojiMatch[1]}</span>`;
                    displayTitle = conversation.title.replace(/^\p{Emoji}/u, '').trim();
                } else {
                    iconHtml = '<span class="conversation-icon">❌</span>';
                }
            }

            // Render delete button for all conversations
            const deleteButtonHtml = `
                <button class="delete-conversation-btn" title="Delete conversation">
                    <i class="fas fa-trash"></i>
                </button>`;

            itemDiv.innerHTML = `
                ${iconHtml}
                <div class="conversation-content">
                    <div class="conversation-title">${this.truncateText(displayTitle, 30)}</div>
                    <div class="conversation-date">${this.formatTime(new Date(conversation.updatedAt))}</div>
                </div>
                ${deleteButtonHtml}
            `;

            // Add click handler to load the conversation
            itemDiv.addEventListener('click', (e) => {
                if (e.target.closest('.delete-conversation-btn')) return;
                this.loadConversation(conversation.id);
            });

            // Add delete button handler
            const deleteBtn = itemDiv.querySelector('.delete-conversation-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteConversation(conversation.id);
                });
            }

            this.elements.conversationList.appendChild(itemDiv);
        });
    }
    
    /**
     * Save the current conversation
     */
    saveCurrentConversation() {
        if (!this.state.currentConversationId) return;
        
        // Find if this conversation already exists
        const existingIndex = this.state.savedConversations.findIndex(
            c => c.id === this.state.currentConversationId
        );
        
        const conversationData = {
            id: this.state.currentConversationId,
            title: this.state.currentTitle || 'Default Saved Title',
            icon: this.state.currentIcon || '💾', // Changed default icon to a save icon
            messages: this.state.messageHistory,
            createdAt: existingIndex >= 0 ? 
            this.state.savedConversations[existingIndex].createdAt : 
            new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        console.log('Saving conversation:', conversationData);
        
        if (existingIndex >= 0) {
            // Update existing conversation
            this.state.savedConversations[existingIndex] = conversationData;
        } else {
            // Add new conversation
            this.state.savedConversations.push(conversationData);
        }
        
        // Save to local storage
        this.saveConversationsToLocalStorage();
        
        // Update the UI
        // this.renderConversationList();
    }
    
    /**
     * Load a conversation by ID
     */
    loadConversation(conversationId) {
        // Find the conversation
        const conversation = this.state.savedConversations.find(c => c.id === conversationId);
        if (!conversation) return;
        
        // Update current conversation ID
        this.state.currentConversationId = conversationId;
        this.state.currentTitle = conversation.title;
        this.state.currentIcon = conversation.icon || '❓';
        
        // Clear the current messages
        while (this.elements.chatMessages.children.length > 1) {
            this.elements.chatMessages.removeChild(this.elements.chatMessages.lastChild);
        }
        
        // Load messages from the conversation
        this.state.messageHistory = [...conversation.messages];
        
        // Display messages
        this.state.messageHistory.forEach(message => {
            this.appendMessage(message.sender, message.content, message.id, message.reference_id, false);
        });
        
        // Update active state in conversation list
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === conversationId);
        });
        
        // Save current conversation ID to local storage
        localStorage.setItem('catalyst_current_conversation', this.state.currentConversationId);
        
        // Scroll to bottom
        this.scrollToBottom();
    }
    
    /**
     * Delete a conversation by ID
     */
    deleteConversation(conversationId) {
        // Remove from array
        this.state.savedConversations = this.state.savedConversations.filter(
            c => c.id !== conversationId
        );
        
        // Save to local storage
        this.saveConversationsToLocalStorage();
        
        // Update UI
        this.renderConversationList();
        
        // If we deleted the current conversation, start a new one
        if (this.state.currentConversationId === conversationId) {
            this.startNewChat(false);
        }
    }
    
    /**
     * Handle input event on chat input
     */
    handleInput(e) {
        // Enable/disable send button based on input
        if (this.elements.chatInput.value.trim().length > 0) {
            this.elements.sendButton.removeAttribute('disabled');
        } else {
            this.elements.sendButton.setAttribute('disabled', 'disabled');
        }
    }
    
    /**
     * Handle keydown event on chat input
     */
    handleKeyDown(e) {
        // Send message on Enter key (without Shift)
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!this.elements.sendButton.hasAttribute('disabled') && !this.state.isProcessing) {
                this.sendMessage();
            }
        }
    }
    
    /**
     * Send a message to the AI
     */
    async sendMessage() {
        if (this.state.isProcessing) return;

        const messageText = this.elements.chatInput.value.trim();
        if (!messageText) return;

        const userMessageId = this.generateId();
        this.appendMessage('user', messageText, userMessageId);

        this.elements.chatInput.value = '';
        this.elements.sendButton.setAttribute('disabled', 'disabled');
        this.elements.chatInput.style.height = 'auto';

        this.state.isProcessing = true;

        this.thinkingMessageId = this.generateId()
        this.appendThinkingMessage(this.thinkingMessageId, userMessageId);

        try {
            if (this.state.eventSource) {
                this.state.eventSource.close();
                this.state.eventSource = null;
            }

            this.state.eventSource = new EventSource('/chat/eventstream');
            this.state.eventSource.onopen = (event) => {
                console.log('SSE connection established');
            }
            this.state.eventSource.onmessage = (event) => {
                console.log('SSE message received:', event.data);
                this.displayEvent(event.data);
            }
            this.state.eventSource.onclose = (event) => {
                console.log('SSE connection closed:', event);
            }

            // Send message to get AI response
            fetch('/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: messageText,
                    messageId: userMessageId,
                    conversation_history: this.state.messageHistory
                })
            });

            this.generateTitle(this.state.messageHistory.filter(msg => msg.sender === 'user'));

        } catch (error) {
            console.error('Error sending message:', error);
            this.removeThinkingMessage(this.thinkingMessageId);
            this.appendErrorMessage('Sorry, there was an error processing your request.');
        } finally {
            this.state.isProcessing = false;
        }
    }
    
    /**
     * Generate a title for the conversation
     */
    async generateTitle(message_history) {
        try {
            const titleResponse = await fetch('/chat/generate_title', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(message_history)
            });
            
            if (!titleResponse.ok) {
                throw new Error(`Title generation failed: ${titleResponse.status} ${titleResponse.statusText}`);
            }
            
            const titleData = await titleResponse.json();

            console.log('Title generation response:', titleData);
            
            if (titleData && titleData.title) {
                // Store the ID we're updating to handle race conditions
                const targetConversationId = this.state.currentConversationId;
                
                // Update the title in the current state
                this.state.currentTitle = titleData.title;
                this.state.currentIcon = titleData.icon || '❓';
                
                // Find the conversation in the saved array
                const index = this.state.savedConversations.findIndex(
                    c => c.id === targetConversationId
                );
                
                console.log('Found conversation at index:', index, 'with ID:', targetConversationId);
                
                if (index !== -1) {
                    const previousTitle = this.state.savedConversations[index].title;
                    console.log('Previous title:', previousTitle);
                    
                    // Verify conversation ID still matches current ID
                    if (this.state.savedConversations[index].id === this.state.currentConversationId) {
                        // Create a deep copy of the savedConversations array to trigger state update
                        const updatedConversations = [...this.state.savedConversations];
                        updatedConversations[index] = {
                            ...updatedConversations[index],
                            title: titleData.title,
                            icon: titleData.icon,
                            updatedAt: new Date().toISOString()
                        };
                        
                        console.log('Updated conversation object:', updatedConversations[index]);
                        
                        // Replace the entire array
                        this.state.savedConversations = updatedConversations;
                        
                        console.log('Updated title to:', this.state.savedConversations[index].title);
                        
                        this.saveCurrentConversation();
                        
                        // Force re-render the conversation list
                        this.renderConversationList();
                    } else {
                        console.warn('Conversation ID mismatch, title update aborted');
                    }
                }
            }
        } catch (error) {
            console.error('Error generating title:', error);
        }
    }
    
    /**
     * Append a "thinking" indicator message
     */
    appendThinkingMessage(messageId, referenceId) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'assistant', 'thinking');
        messageDiv.dataset.id = messageId;
        
        if (referenceId) {
            messageDiv.dataset.referenceId = referenceId;
        }
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="event-tags"></div>
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        this.elements.chatMessages.appendChild(messageDiv);
        
        // Scroll to the new message
        this.scrollToBottom();
    }

    displayEvent(eventData) {
        // Get a reference to the chat app instance
        const chatApp = window.chatAppInstance;
        
        if (!chatApp) {
            console.error('Chat app instance not available');
            return;
        }
        
        try {
            // Parse the event data
            const eventObj = JSON.parse(eventData);
            
            // Initialize events array for the current message if needed
            if (!chatApp.state.currentEvents) {
                chatApp.state.currentEvents = [];
            }
            
            // Determine event type and icon/message
            let eventTypeClass = 'event-default';
            let eventIcon = 'ℹ️';
            let eventMessage = 'event';
            
            if (eventObj.event_type) {
                switch(eventObj.event_type.toLowerCase()) {
                    case 'tool_input':
                        return;
                    case 'tool_output':
                        eventTypeClass = 'event-tool';
                        eventIcon = '🔧';
                        eventMessage = eventObj.metadata?.tool_name || 'tool';
                        break;
                    case 'language_operations':
                        eventTypeClass = 'event-language-skills';
                        eventIcon = '🧠';
                        eventMessage = "llm";
                        break;
                    case 'plan_generation':
                        eventTypeClass = 'event-plan';
                        eventIcon = '📊';
                        eventMessage = "plan";
                        break;
                    case 'plan_change':
                        eventTypeClass = 'event-replan';
                        eventIcon = '🔄';
                        eventMessage = "replan";
                        break;
                    case 'final_solution':
                        // Handle final solution event
                        if (this.state.eventSource) {
                            this.state.eventSource.close();
                            this.state.eventSource = null;
                        }
    
                        // Process message response
                        this.removeThinkingMessage(this.thinkingMessageId);
                        this.appendMessage('assistant', eventObj.data.solution, eventObj.metadata.message_id);
                        
                        // Save conversation with current messages
                        this.saveCurrentConversation();
                        return;
                    default:
                        return; // Ignore unknown event types
                }
            
                // Add event to the current events array
                chatApp.state.currentEvents.push({
                    type: eventTypeClass,
                    icon: eventIcon,
                    message: eventMessage,
                    timestamp: new Date(),
                    data: eventObj
                });
                
                // Find any thinking message that might need to have tags added
                const thinkingMessage = document.querySelector('.message.assistant.thinking');
                if (thinkingMessage) {
                    // Update or create the event tags container
                    let eventTagsContainer = thinkingMessage.querySelector('.event-tags');
                    if (!eventTagsContainer) {
                        eventTagsContainer = document.createElement('div');
                        eventTagsContainer.className = 'event-tags';
                        
                        // Insert at the top of the message content
                        const messageContent = thinkingMessage.querySelector('.message-content');
                        if (messageContent) {
                            messageContent.insertBefore(eventTagsContainer, messageContent.firstChild);
                        }
                    }
                    
                    // Add the new event tag
                    const eventTag = document.createElement('span');
                    eventTag.className = `event-tag ${eventTypeClass}`;
                    eventTag.title = JSON.stringify(eventObj, null, 2);
                    eventTag.innerHTML = `<span class="event-icon">${eventIcon}</span><span class="event-label">${eventMessage}</span>`;
                    
                    // Add to the container
                    eventTagsContainer.appendChild(eventTag);
                }
                
                // Store the event in the chat app's state for later use
                if (!chatApp.state.events) {
                    chatApp.state.events = {};
                }
                
                // Store events by reference ID to ensure they're preserved
                const referenceId = thinkingMessage?.dataset?.referenceId;
                if (referenceId) {
                    if (!chatApp.state.events[referenceId]) {
                        chatApp.state.events[referenceId] = [];
                    }
                    chatApp.state.events[referenceId].push({
                        type: eventTypeClass,
                        icon: eventIcon,
                        message: eventMessage,
                        data: eventObj,
                        html: `<span class="event-tag ${eventTypeClass}" title='${JSON.stringify(eventObj, null, 2).replace(/'/g, "&apos;")}'>
                            <span class="event-icon">${eventIcon}</span><span class="event-label">${eventMessage}</span>
                        </span>`
                    });
                }
            }
            
        } catch (error) {
            console.error('Error processing event data:', error, eventData);
        }
    }
    
    
    /**
     * Remove a thinking message by ID
     */
    removeThinkingMessage(messageId) {
        const thinkingMessage = document.querySelector(`.message[data-id="${messageId}"]`);
        if (thinkingMessage) {
            thinkingMessage.remove();
        }
    }
    
    /**
     * Append a new message to the chat
     */
    appendMessage(sender, content, messageId, referenceId = null, shouldSave = true) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.dataset.id = messageId;
        
        if (referenceId) {
            messageDiv.dataset.referenceId = referenceId;
        }
        
        // Store message in history if this is a new message
        if (shouldSave) {
            this.state.messageHistory.push({
                id: messageId,
                sender: sender,
                content: content,
                timestamp: new Date().toISOString(),
                reference_id: referenceId
            });
        }
        
        // Create message content
        let formattedContent = content;
        
        // Format markdown content if it's from the assistant
        if (sender === 'assistant') {
            // Replace \[ and \] with $$, Replace \( and \) with $
            formattedContent = formattedContent.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$')
            formattedContent = formattedContent.replace(/\\\(/g, '$').replace(/\\\)/g, '$');
            // replace sandbox: with website url
            formattedContent = formattedContent.replace(/sandbox:/g, 'http://localhost:5000/');
            formattedContent = this.formatMarkdown(formattedContent);
        }
        
        // Add edit button only for user messages
        const editButton = sender === 'user' ? 
            `<button class="edit-message-btn" title="Edit message">
                <i class="fas fa-edit"></i>
            </button>` : '';
        
        // Add copy button to all messages
        const copyButton = `<button class="copy-message-btn" title="Copy message">
            <i class="fas fa-copy"></i>
        </button>`;
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-${sender === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">
                ${sender === 'assistant' ? '<div class="event-tags"></div>' : ''}
                <div class="message-text">${formattedContent}</div>
                <div class="message-footer">
                    <div class="message-time">${this.formatTime(new Date())}</div>
                    <div class="message-actions">
                        ${copyButton}
                        ${editButton}
                    </div>
                </div>
            </div>
        `;

        // Update message text with Latex rendering
        const messageTextContainer = messageDiv.querySelector('.message-text');
        renderMathInElement(messageTextContainer, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\[', right: '\\]', display: true},
                {left: '\\(', right: '\\)', display: false},
            ],
            throwOnError: false
        })
        
        // Add event listener for edit button if this is a user message
        if (sender === 'user') {
            const editBtn = messageDiv.querySelector('.edit-message-btn');
            editBtn.addEventListener('click', () => {
                this.startEditingMessage(messageDiv, messageId, content);
            });
        }
        
        // Add event listener for copy button
        const copyBtn = messageDiv.querySelector('.copy-message-btn');
        copyBtn.addEventListener('click', () => {
            this.copyMessageToClipboard(messageDiv, content);
        });
        
        // If this is an assistant message that replaces a thinking message, transfer any event tags
        if (sender === 'assistant' && referenceId) {
            // Method 1: Try to get tags from thinking message in the DOM
            const thinkingMessage = document.querySelector(`.message.assistant.thinking[data-reference-id="${referenceId}"]`);
            if (thinkingMessage) {
                const eventTags = thinkingMessage.querySelector('.event-tags');
                if (eventTags) {
                    const newEventTags = messageDiv.querySelector('.event-tags');
                    if (newEventTags && eventTags.children.length > 0) {
                        // Clone the event tags from the thinking message
                        Array.from(eventTags.children).forEach(tagElement => {
                            newEventTags.appendChild(tagElement.cloneNode(true));
                        });
                    }
                }
            }
            
            // Method 2: Check for events stored by reference ID in state
            if (this.state.events && this.state.events[referenceId]) {
                const newEventTags = messageDiv.querySelector('.event-tags');
                
                // Skip if we already copied events from the thinking message
                if (newEventTags && newEventTags.children.length === 0) {
                    // Create event tags from stored data
                    this.state.events[referenceId].forEach(event => {
                        if (event.html) {
                            // Create tag from stored HTML
                            const tagContainer = document.createElement('div');
                            tagContainer.innerHTML = event.html;
                            const tagElement = tagContainer.firstChild;
                            newEventTags.appendChild(tagElement);
                        } else {
                            // Create tag from event data
                            const tagElement = document.createElement('span');
                            tagElement.className = `event-tag ${event.type}`;
                            tagElement.title = JSON.stringify(event.data, null, 2);
                            tagElement.innerHTML = `<span class="event-icon">${event.icon}</span><span class="event-label">${event.message}</span>`;
                            newEventTags.appendChild(tagElement);
                        }
                    });
                }
            }
        }
        
        this.elements.chatMessages.appendChild(messageDiv);
        
        // Scroll to the new message
        this.scrollToBottom();
    }
    
    /**
     * Start editing a message
     */
    startEditingMessage(messageElement, messageId, content) {
        if (this.state.isProcessing) return;

        this.state.isEditing = true;
        this.state.currentEditId = messageId;

        const messageTextContainer = messageElement.querySelector('.message-text');
        const messageContentContainer = messageElement.querySelector('.message-content');
        const originalContent = content;

        const originalWidth = messageContentContainer.offsetWidth;

        messageElement.classList.add('editing');
        messageContentContainer.style.width = originalWidth + 'px';

        // Hide copy and edit buttons during editing
        const messageActions = messageElement.querySelector('.message-actions');
        if (messageActions) {
            messageActions.style.display = 'none';
        }

        messageTextContainer.innerHTML = `
            <textarea class="edit-message-textarea">${originalContent}</textarea>
            <div class="edit-actions">
                <button class="save-edit-btn" title="Save edit">
                    <i class="fas fa-check"></i>
                </button>
                <button class="cancel-edit-btn" title="Cancel edit">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        const textarea = messageTextContainer.querySelector('.edit-message-textarea');
        textarea.focus();
        textarea.style.paddingBottom = '32px';
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;

        const saveBtn = messageTextContainer.querySelector('.save-edit-btn');
        const cancelBtn = messageTextContainer.querySelector('.cancel-edit-btn');

        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.saveEdit(messageElement, messageId, textarea.value);
            } else if (e.key === 'Escape') {
                this.cancelEdit(messageElement, originalContent);
            }
        });

        saveBtn.addEventListener('click', () => {
            this.saveEdit(messageElement, messageId, textarea.value);
        });

        cancelBtn.addEventListener('click', () => {
            this.cancelEdit(messageElement, originalContent);
        });
    }
    
    /**
     * Cancel editing a message
     */
    cancelEdit(messageElement, originalContent) {
        this.state.isEditing = false;
        this.state.currentEditId = null;

        const messageTextContainer = messageElement.querySelector('.message-text');
        messageElement.classList.remove('editing');
        messageTextContainer.innerHTML = originalContent;

        const messageActions = messageElement.querySelector('.message-actions');
        if (messageActions) {
            messageActions.style.display = '';
        }
    }

    /**
     * Save an edited message
     */
    saveEdit(messageElement, messageId, newContent) {
        if (!newContent.trim()) {
            this.cancelEdit(messageElement, newContent);
            return;
        }

        const messageIndex = this.state.messageHistory.findIndex(msg => msg.id === messageId);
        if (messageIndex === -1) return;

        this.state.messageHistory[messageIndex].content = newContent;

        this.state.isEditing = false;

        const messageTextContainer = messageElement.querySelector('.message-text');
        messageElement.classList.remove('editing');
        messageTextContainer.innerHTML = newContent;

        const messageActions = messageElement.querySelector('.message-actions');
        if (messageActions) {
            messageActions.style.display = '';
        }

        // Remove subsequent DOM elements directly
        // console.log(`Editing message ID: ${messageId}. Removing subsequent DOM elements.`); // Keep commented out or remove
        let nextSibling = messageElement.nextElementSibling;
        while (nextSibling) {
            const siblingToRemove = nextSibling;
            nextSibling = nextSibling.nextElementSibling; // Get next before removing current
            // console.log(`Removing DOM element with ID: ${siblingToRemove.dataset.id}`); // Keep commented out or remove
            siblingToRemove.remove();
        }

        // Update the message history by removing subsequent messages (this part was correct)
        // const originalHistoryLength = this.state.messageHistory.length; // Keep commented out or remove
        this.state.messageHistory = this.state.messageHistory.slice(0, messageIndex + 1);
        // console.log(`History truncated from ${originalHistoryLength} to ${this.state.messageHistory.length} messages. Last message ID: ${this.state.messageHistory[this.state.messageHistory.length - 1]?.id}`); // Keep commented out or remove

        this.saveCurrentConversation();

        this.state.isProcessing = true;
        this.reSendEditedMessage(newContent, messageId);
    }
    
    /**
     * Re-send an edited message to get updated response
     */
    async reSendEditedMessage(messageText, messageId) {
        try {
            console.log('Re-sending edited message:', messageText, 'with ID:', messageId);
            // Store the edited message ID for reference
            this.state.editedMessageId = messageId;
            
            // The message history should already be correctly truncated by saveEdit.
            // We keep the original history copy only for potential error recovery.
            const originalHistory = [...this.state.messageHistory];
            
            // No need to filter history again here as saveEdit handles it.
            
            // Set up for processing new message
            this.state.isProcessing = true;
            
            // Add a thinking message with the typing indicator
            this.thinkingMessageId = this.generateId();
            this.appendThinkingMessage(this.thinkingMessageId, messageId);
            
            // Use the existing fetch call pattern from sendMessage
            try {
                if (this.state.eventSource) {
                    this.state.eventSource.close();
                    this.state.eventSource = null;
                }
    
                this.state.eventSource = new EventSource('/chat/eventstream');
                this.state.eventSource.onopen = (event) => {
                    console.log('SSE connection established');
                }
                this.state.eventSource.onmessage = (event) => {
                    console.log('SSE message received:', event.data);
                    this.displayEvent(event.data);
                }
                this.state.eventSource.onclose = (event) => {
                    console.log('SSE connection closed:', event);
                }
    
                // Send edited message to get AI response
                fetch('/chat/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: messageText,
                        messageId: messageId,
                        conversation_history: this.state.messageHistory
                    })
                });
    
                // We don't need to generate a title for edited messages
                
            } catch (error) {
                console.error('Error sending edited message:', error);
                this.removeThinkingMessage(this.thinkingMessageId);
                this.appendErrorMessage('Sorry, there was an error processing your edited message.');
                
                // Restore original history
                this.state.messageHistory = originalHistory;
            }
            
        } catch (error) {
            console.error('Error in reSendEditedMessage:', error);
            this.removeThinkingMessage(this.thinkingMessageId);
            this.appendErrorMessage('Sorry, there was an error processing your edited message.');
        } finally {
            this.state.isProcessing = false;
            this.state.editedMessageId = null;
        }
    }
    
    /**
     * Append an error message to the chat
     */
    appendErrorMessage(errorText) {
        const errorDiv = document.createElement('div');
        errorDiv.classList.add('message', 'system', 'error');
        
        errorDiv.innerHTML = `
            <div class="message-content">
                <p>${errorText}</p>
            </div>
        `;
        
        this.elements.chatMessages.appendChild(errorDiv);
        this.scrollToBottom();
    }
    
    /**
     * Format markdown text to HTML
     */
    formatMarkdown(text) {
        // Use marked.js to convert markdown to HTML
        let htmlContent = marked.parse(text);

        // Function to handle mermaid code blocks
        const handleMermaid = (element) => {
            element.querySelectorAll('pre code.language-mermaid').forEach((block) => {
                // Create a container for the mermaid diagram
                const mermaidContainer = document.createElement('div');
                mermaidContainer.className = 'mermaid';
                mermaidContainer.innerHTML = block.textContent;

                // Replace the code block with the mermaid container
                block.parentNode.parentNode.replaceChild(mermaidContainer, block.parentNode);
            });
            mermaid.contentLoaded();
        };

        // After converting to HTML, initialize syntax highlighting
        setTimeout(() => {
            document.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightBlock(block);
            });
            handleMermaid(document);
        }, 0);

        return htmlContent;
    }
    
    /**
     * Scroll the chat container to the bottom
     */
    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    /**
     * Clear the current chat
     */
    clearChat() {
        if (confirm('Are you sure you want to clear this conversation? This cannot be undone.')) {
            // Clear the chat messages (except the system greeting)
            while (this.elements.chatMessages.children.length > 1) {
                this.elements.chatMessages.removeChild(this.elements.chatMessages.lastChild);
            }
            
            // Clear message history
            this.state.messageHistory = [];
            
            // Save the cleared state
            this.saveCurrentConversation();
            
            // Focus on input
            this.elements.chatInput.focus();
        }
    }
    
    /**
     * Export the current chat as a JSON file
     */
    exportChat() {
        // Create exportable content
        const exportData = {
            id: this.state.currentConversationId,
            timestamp: new Date().toISOString(),
            messages: this.state.messageHistory
        };
        
        // Convert to JSON string
        const jsonString = JSON.stringify(exportData, null, 2);
        
        // Create download link
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `catalyst-chat-${this.formatDateForFilename(new Date())}.json`;
        document.body.appendChild(a);
        a.click();
        
        // Cleanup
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    clearChatHistory() {
            // Clear the chat interface
            while (this.elements.chatMessages.children.length > 1) {
                this.elements.chatMessages.removeChild(this.elements.chatMessages.lastChild);
            }
            
            // Reset message history
            this.state.messageHistory = [];    
    }

    /**
     * Start a new chat conversation
     */
    startNewChat(shouldSwitchToNew = true) {
        // If we should switch to new chat (not just initializing)
        if (shouldSwitchToNew) {
            // Save the current conversation first if it has messages
            if (this.state.messageHistory.length > 0)
                this.saveCurrentConversation();
            
            this.clearChatHistory();
        }
        
        // Create new conversation ID
        this.state.currentConversationId = this.generateId();
        this.state.currentTitle = "New Conversation";
        this.state.currentIcon = "💬";

        // Create a new conversation in the savedConversations array
        const newConversation = {
            id: this.state.currentConversationId,
            title: this.state.currentTitle,
            icon: this.state.currentIcon,
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        // Add the new conversation to the array
        this.state.savedConversations.push(newConversation);
        
        // Save to local storage
        // this.saveConversationsToLocalStorage();
        
        // Render the conversation list
        this.renderConversationList();
        
        // Focus on input
        this.elements.chatInput.focus();
    }
    
    /**
     * Copy message content to clipboard
     */
    copyMessageToClipboard(messageDiv, content) {
        // For assistant messages, we need to get the plain text version of the HTML content
        if (messageDiv.classList.contains('assistant')) {
            // Create temporary element to extract text from HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = content;
            content = tempDiv.textContent || tempDiv.innerText || '';
        }
        
        // Use the clipboard API if available
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(content)
                .then(() => {
                    // Show a visual feedback for copy
                    const copyBtn = messageDiv.querySelector('.copy-message-btn');
                    const originalIcon = copyBtn.innerHTML;
                    copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                    
                    // Reset the icon after 2 seconds
                    setTimeout(() => {
                        copyBtn.innerHTML = originalIcon;
                    }, 2000);
                })
                .catch(err => {
                    console.error('Could not copy text: ', err);
                    // Fallback to the older method
                    this.copyWithExecCommand(content);
                });
        } else {
            // Fallback for browsers that don't support clipboard API
            this.copyWithExecCommand(content);
        }
    }
    
    /**
     * Fallback method for copying text
     */
    copyWithExecCommand(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';  // Prevent scrolling to the element
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            console.log('Text copied to clipboard');
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
        document.body.removeChild(textarea);
    }
    
    /**
     * Auto-resize a textarea as the user types
     */
    autoResizeTextarea(textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
    
    // Utility methods
    
    /**
     * Generate a random ID
     */
    generateId() {
        return 'conv_' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Format a date as time string
     */
    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    /**
     * Format a date for filename
     */
    formatDateForFilename(date) {
        return date.toISOString().split('T')[0];
    }
    
    /**
     * Truncate text with ellipsis
     */
    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }
}