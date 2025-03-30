/**
 * Catalyst AI Web UI - Chat JavaScript
 * This file handles the chat interface functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-message');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const clearChatButton = document.getElementById('clear-chat');
    const exportChatButton = document.getElementById('export-chat');
    const newChatButton = document.getElementById('new-chat');
    const conversationList = document.getElementById('conversation-list');
    
    // Chat state
    let isProcessing = false;
    let messageHistory = [];
    let currentConversationId = null;
    let isEditing = false;
    let currentEditId = null;
    let savedConversations = [];
    
    // Initialize
    init();
    
    function init() {
        // Load saved conversations from local storage
        loadSavedConversations();
        
        // Create or load a conversation
        if (!currentConversationId) {
            startNewChat(false);
        } else {
            loadConversation(currentConversationId);
        }
        
        // Add event listeners
        chatInput.addEventListener('input', handleInput);
        chatInput.addEventListener('keydown', handleKeyDown);
        sendButton.addEventListener('click', sendMessage);
        clearChatButton.addEventListener('click', clearChat);
        exportChatButton.addEventListener('click', exportChat);
        newChatButton.addEventListener('click', () => startNewChat(true));
        
        // Auto-resize textarea as user types
        autoResizeTextarea(chatInput);
    }
    
    // Function to load saved conversations from local storage
    function loadSavedConversations() {
        try {
            const savedConvsJson = localStorage.getItem('catalyst_conversations');
            if (savedConvsJson) {
                savedConversations = JSON.parse(savedConvsJson);
                
                // Load last active conversation ID
                currentConversationId = localStorage.getItem('catalyst_current_conversation');
                
                // Populate conversation list in sidebar
                renderConversationList();
            }
        } catch (error) {
            console.error('Error loading saved conversations:', error);
            savedConversations = [];
        }
    }
    
    // Function to save conversations to local storage
    function saveConversationsToLocalStorage() {
        try {
            localStorage.setItem('catalyst_conversations', JSON.stringify(savedConversations));
            localStorage.setItem('catalyst_current_conversation', currentConversationId);
        } catch (error) {
            console.error('Error saving conversations to local storage:', error);
        }
    }
    
    // Function to render the conversation list in the sidebar
    function renderConversationList() {
        // Clear the list first
        conversationList.innerHTML = '';
        
        if (savedConversations.length === 0) {
            conversationList.innerHTML = '<div class="empty-state"><p>No conversations yet</p></div>';
            return;
        }
        
        // Sort conversations by last updated date (newest first)
        const sortedConversations = [...savedConversations].sort((a, b) => 
            new Date(b.updatedAt) - new Date(a.updatedAt)
        );
        
        // Add each conversation to the list
        sortedConversations.forEach(conversation => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('conversation-item');
            if (conversation.id === currentConversationId) {
                itemDiv.classList.add('active');
            }
            itemDiv.dataset.id = conversation.id;
            
            itemDiv.innerHTML = `
                <div class="conversation-title">${truncateText(conversation.title, 30)}</div>
                <div class="conversation-date">${formatTime(new Date(conversation.updatedAt))}</div>
                <button class="delete-conversation-btn" title="Delete conversation">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            
            // Add click handler to load the conversation
            itemDiv.addEventListener('click', (e) => {
                // Don't trigger if clicking the delete button
                if (e.target.closest('.delete-conversation-btn')) return;
                loadConversation(conversation.id);
            });
            
            // Add delete button handler
            const deleteBtn = itemDiv.querySelector('.delete-conversation-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteConversation(conversation.id);
            });
            
            conversationList.appendChild(itemDiv);
        });
    }
    
    // Function to save the current conversation
    function saveCurrentConversation(title) {
        if (!currentConversationId) return;
        
        // Find if this conversation already exists
        const existingIndex = savedConversations.findIndex(c => c.id === currentConversationId);
        
        const conversationData = {
            id: currentConversationId,
            title: title || 'New Conversation',
            messages: messageHistory,
            createdAt: existingIndex >= 0 ? savedConversations[existingIndex].createdAt : new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        if (existingIndex >= 0) {
            // Update existing conversation
            savedConversations[existingIndex] = conversationData;
        } else {
            // Add new conversation
            savedConversations.push(conversationData);
        }
        
        // Save to local storage
        saveConversationsToLocalStorage();
        
        // Update the UI
        renderConversationList();
    }
    
    // Function to load a conversation
    function loadConversation(conversationId) {
        // Find the conversation
        const conversation = savedConversations.find(c => c.id === conversationId);
        if (!conversation) return;
        
        // Update current conversation ID
        currentConversationId = conversationId;
        
        // Clear the current messages
        while (chatMessages.children.length > 1) {
            chatMessages.removeChild(chatMessages.lastChild);
        }
        
        // Load messages from the conversation
        messageHistory = [...conversation.messages];
        
        // Display messages
        messageHistory.forEach(message => {
            appendMessage(message.sender, message.content, message.id, message.reference_id, false);
        });
        
        // Update active state in conversation list
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === conversationId);
        });
        
        // Save current conversation ID to local storage
        localStorage.setItem('catalyst_current_conversation', currentConversationId);
        
        // Scroll to bottom
        scrollToBottom();
    }
    
    // Function to delete a conversation
    function deleteConversation(conversationId) {
        // Remove from array
        savedConversations = savedConversations.filter(c => c.id !== conversationId);
        
        // Save to local storage
        saveConversationsToLocalStorage();
        
        // Update UI
        renderConversationList();
        
        // If we deleted the current conversation, start a new one
        if (currentConversationId === conversationId) {
            startNewChat(false);
        }
    }
    
    function handleInput(e) {
        // Enable/disable send button based on input
        if (chatInput.value.trim().length > 0) {
            sendButton.removeAttribute('disabled');
        } else {
            sendButton.setAttribute('disabled', 'disabled');
        }
    }
    
    function handleKeyDown(e) {
        // Send message on Enter key (without Shift)
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.hasAttribute('disabled') && !isProcessing) {
                sendMessage();
            }
        }
    }
    
    async function sendMessage() {
        if (isProcessing) return;
        
        const messageText = chatInput.value.trim();
        if (!messageText) return;
        
        // Generate an ID for the user message
        const userMessageId = generateId();
        
        // Show user message
        appendMessage('user', messageText, userMessageId);
        
        // Clear input and disable button
        chatInput.value = '';
        sendButton.setAttribute('disabled', 'disabled');
        chatInput.style.height = 'auto';
        
        // Show thinking bubble with typing indicator instead of the standalone indicator
        isProcessing = true;
        
        // Add a thinking message with the typing indicator
        const thinkingMessageId = generateId();
        appendThinkingMessage(thinkingMessageId, userMessageId);
        
        try {
            // Send message to server with the message ID
            const response = await fetch('/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    message: messageText,
                    messageId: userMessageId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Remove thinking message
            removeThinkingMessage(thinkingMessageId);
            
            // Show AI response
            appendMessage('assistant', data.content, data.id, userMessageId);
            
            // Save the conversation after new messages
            const firstUserMessage = messageHistory.find(msg => msg.sender === 'user');
            saveCurrentConversation(firstUserMessage ? firstUserMessage.content : 'New Conversation');
            
        } catch (error) {
            console.error('Error sending message:', error);
            // Remove thinking message
            removeThinkingMessage(thinkingMessageId);
            appendErrorMessage('Sorry, there was an error processing your request.');
        } finally {
            isProcessing = false;
        }
    }
    
    // New function to append a thinking message with typing indicator
    function appendThinkingMessage(messageId, referenceId) {
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
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to the new message
        scrollToBottom();
    }
    
    // Function to remove thinking message
    function removeThinkingMessage(messageId) {
        const thinkingMessage = document.querySelector(`.message[data-id="${messageId}"]`);
        if (thinkingMessage) {
            thinkingMessage.remove();
        }
    }
    
    function appendMessage(sender, content, messageId, referenceId = null, shouldSave = true) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.dataset.id = messageId;
        
        if (referenceId) {
            messageDiv.dataset.referenceId = referenceId;
        }
        
        // Store message in history if this is a new message
        if (shouldSave) {
            messageHistory.push({
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
            formattedContent = formatMarkdown(content);
        }
        
        // Add edit button only for user messages
        const editButton = sender === 'user' ? 
            `<button class="edit-message-btn" title="Edit message">
                <i class="fas fa-edit"></i>
            </button>` : '';
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-${sender === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">
                <div class="message-text">${formattedContent}</div>
                <div class="message-time">${formatTime(new Date())}</div>
                ${editButton}
            </div>
        `;
        
        // Add event listener for edit button if this is a user message
        if (sender === 'user') {
            const editBtn = messageDiv.querySelector('.edit-message-btn');
            editBtn.addEventListener('click', () => {
                startEditingMessage(messageDiv, messageId, content);
            });
        }
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to the new message
        scrollToBottom();
    }
    
    // New function to start editing a message
    function startEditingMessage(messageElement, messageId, content) {
        // Don't allow editing if we're already processing a message
        if (isProcessing) return;
        
        isEditing = true;
        currentEditId = messageId;
        
        // Get the message text container
        const messageTextContainer = messageElement.querySelector('.message-text');
        const originalContent = content;
        
        // Replace the message content with an editable textarea
        messageElement.classList.add('editing');
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
        
        // Get the textarea and focus it
        const textarea = messageTextContainer.querySelector('.edit-message-textarea');
        textarea.focus();
        
        // Add padding at the bottom of the textarea to make room for the buttons
        textarea.style.paddingBottom = '32px';
        
        // Position the cursor at the end of the text
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
        
        // Add event listeners for saving and canceling edit
        const saveBtn = messageTextContainer.querySelector('.save-edit-btn');
        const cancelBtn = messageTextContainer.querySelector('.cancel-edit-btn');
        
        // Handle Enter key to save
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                saveEdit(messageElement, messageId, textarea.value);
            } else if (e.key === 'Escape') {
                cancelEdit(messageElement, originalContent);
            }
        });
        
        saveBtn.addEventListener('click', () => {
            saveEdit(messageElement, messageId, textarea.value);
        });
        
        cancelBtn.addEventListener('click', () => {
            cancelEdit(messageElement, originalContent);
        });
    }
    
    // Improved function to save edited message
    function saveEdit(messageElement, messageId, newContent) {
        // If content is empty or unchanged, just cancel
        if (!newContent.trim()) {
            cancelEdit(messageElement, newContent);
            return;
        }
        
        // Find the index of this message in history
        const messageIndex = messageHistory.findIndex(msg => msg.id === messageId);
        if (messageIndex === -1) return;
        
        // Update the message content in memory
        const originalContent = messageHistory[messageIndex].content;
        
        // If content didn't change, just cancel edit
        if (originalContent === newContent) {
            cancelEdit(messageElement, originalContent);
            return;
        }
        
        // Update the message in the history
        messageHistory[messageIndex].content = newContent;
        
        // Finish editing mode
        isEditing = false;
        
        // Get the text container
        const messageTextContainer = messageElement.querySelector('.message-text');
        messageElement.classList.remove('editing');
        messageTextContainer.innerHTML = newContent;
        
        // Find the next message (the bot response)
        const nextMessage = document.querySelector(`.message[data-reference-id="${messageId}"]`);
        
        if (nextMessage) {
            // Remove all messages after this response
            let currentElement = nextMessage;
            while (currentElement) {
                const nextEl = currentElement.nextElementSibling;
                currentElement.remove();
                currentElement = nextEl;
            }
            
            // Also remove those messages from history
            const responseIndex = messageHistory.findIndex(msg => msg.id === nextMessage.dataset.id);
            if (responseIndex !== -1) {
                messageHistory = messageHistory.slice(0, responseIndex);
            }
            
            // Save the current conversation state
            const firstUserMessage = messageHistory.find(msg => msg.sender === 'user');
            saveCurrentConversation(firstUserMessage ? firstUserMessage.content : 'New Conversation');
            
            // Add a typing indicator to show we're processing
            typingIndicator.classList.add('active');
            isProcessing = true;
            
            // Send the edited message to the backend
            reSendEditedMessage(newContent, messageId);
        }
    }
    
    // New function to cancel editing
    function cancelEdit(messageElement, originalContent) {
        isEditing = false;
        currentEditId = null;
        
        // Get the text container
        const messageTextContainer = messageElement.querySelector('.message-text');
        messageElement.classList.remove('editing');
        messageTextContainer.innerHTML = originalContent;
    }
    
    // New function to resend the edited message to the backend
    async function reSendEditedMessage(messageText, messageId) {
        try {
            // Add a thinking message with the typing indicator
            const thinkingMessageId = generateId();
            appendThinkingMessage(thinkingMessageId, messageId);
            
            // Send message to server
            const response = await fetch('/chat/edit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    message: messageText,
                    messageId: messageId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Remove thinking message
            removeThinkingMessage(thinkingMessageId);
            
            // Show AI response
            appendMessage('assistant', data.content, data.id, messageId);
            
            // Save the conversation after the edit
            const firstUserMessage = messageHistory.find(msg => msg.sender === 'user');
            saveCurrentConversation(firstUserMessage ? firstUserMessage.content : 'New Conversation');
            
        } catch (error) {
            console.error('Error sending edited message:', error);
            removeThinkingMessage(thinkingMessageId);
            appendErrorMessage('Sorry, there was an error processing your edited message.');
        } finally {
            isProcessing = false;
        }
    }
    
    function appendErrorMessage(errorText) {
        const errorDiv = document.createElement('div');
        errorDiv.classList.add('message', 'system', 'error');
        
        errorDiv.innerHTML = `
            <div class="message-content">
                <p>${errorText}</p>
            </div>
        `;
        
        chatMessages.appendChild(errorDiv);
        scrollToBottom();
    }
    
    function formatMarkdown(text) {
        // Use marked.js to convert markdown to HTML
        const htmlContent = marked.parse(text);
        
        // After converting to HTML, initialize syntax highlighting
        setTimeout(() => {
            document.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }, 0);
        
        return htmlContent;
    }
    
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function clearChat() {
        if (confirm('Are you sure you want to clear this conversation? This cannot be undone.')) {
            // Clear the chat messages (except the system greeting)
            while (chatMessages.children.length > 1) {
                chatMessages.removeChild(chatMessages.lastChild);
            }
            
            // Clear message history
            messageHistory = [];
            
            // Save the cleared state
            saveCurrentConversation('New Conversation');
            
            // Focus on input
            chatInput.focus();
        }
    }
    
    function exportChat() {
        // Create exportable content
        const exportData = {
            id: currentConversationId,
            timestamp: new Date().toISOString(),
            messages: messageHistory
        };
        
        // Convert to JSON string
        const jsonString = JSON.stringify(exportData, null, 2);
        
        // Create download link
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `catalyst-chat-${formatDateForFilename(new Date())}.json`;
        document.body.appendChild(a);
        a.click();
        
        // Cleanup
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    function startNewChat(shouldSwitchToNew = true) {
        // If we should switch to new chat (not just initializing)
        if (shouldSwitchToNew) {
            // Save the current conversation first if it has messages
            if (messageHistory.length > 0) {
                const firstUserMessage = messageHistory.find(msg => msg.sender === 'user');
                saveCurrentConversation(firstUserMessage ? firstUserMessage.content : 'New Conversation');
            }
            
            // Clear the chat interface
            while (chatMessages.children.length > 1) {
                chatMessages.removeChild(chatMessages.lastChild);
            }
            
            // Reset message history
            messageHistory = [];
        }
        
        // Create new conversation ID
        currentConversationId = generateId();
        
        // Add this new conversation to the saved list
        saveCurrentConversation('New Conversation');
        
        // Focus on input
        chatInput.focus();
    }
    
    async function fetchChatHistory() {
        // Don't fetch from server if we have a conversation in local storage
        if (savedConversations.length > 0 && currentConversationId) {
            return;
        }
        
        try {
            const response = await fetch('/chat/history');
            if (!response.ok) {
                throw new Error('Failed to fetch chat history');
            }
            
            const data = await response.json();
            
            // If we have history, display it
            if (data && data.length > 0) {
                // Clear the existing messages (except the system greeting)
                while (chatMessages.children.length > 1) {
                    chatMessages.removeChild(chatMessages.lastChild);
                }
                
                // Add messages from history
                messageHistory = data;
                
                // Display messages
                for (let i = 0; i < data.length; i++) {
                    const message = data[i];
                    appendMessage(message.sender, message.content, message.id, message.reference_id, false);
                }
                
                // Create a new conversation in local storage
                const firstUserMessage = data.find(msg => msg.sender === 'user');
                saveCurrentConversation(firstUserMessage ? firstUserMessage.content : 'Imported Conversation');
            }
        } catch (error) {
            console.error('Error fetching chat history:', error);
        }
    }
    
    // Utility functions
    function generateId() {
        return 'conv_' + Math.random().toString(36).substr(2, 9);
    }
    
    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    function formatDateForFilename(date) {
        return date.toISOString().split('T')[0];
    }
    
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }
    
    function autoResizeTextarea(textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
    
    // Setup Server-Sent Events for streaming responses
    function setupSSE() {
        const evtSource = new EventSource('/chat/stream');
        
        evtSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('SSE message:', data);
            // Here you would handle streamed responses
            // This will be implemented in the future for streaming responses
        };
        
        evtSource.onerror = function(err) {
            console.error('SSE error:', err);
            evtSource.close();
        };
    }
    
    // Uncomment to enable SSE streaming when ready
    // setupSSE();
});