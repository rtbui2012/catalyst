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
    let currentConversationId = generateId();
    
    // Initialize
    init();
    
    function init() {
        // Fetch chat history from the server
        fetchChatHistory();
        
        // Add event listeners
        chatInput.addEventListener('input', handleInput);
        chatInput.addEventListener('keydown', handleKeyDown);
        sendButton.addEventListener('click', sendMessage);
        clearChatButton.addEventListener('click', clearChat);
        exportChatButton.addEventListener('click', exportChat);
        newChatButton.addEventListener('click', startNewChat);
        
        // Auto-resize textarea as user types
        autoResizeTextarea(chatInput);
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
        
        // Show user message
        const userMessageId = generateId();
        appendMessage('user', messageText, userMessageId);
        
        // Clear input and disable button
        chatInput.value = '';
        sendButton.setAttribute('disabled', 'disabled');
        chatInput.style.height = 'auto';
        
        // Show typing indicator
        isProcessing = true;
        typingIndicator.classList.add('active');
        
        try {
            // Send message to server
            const response = await fetch('/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: messageText })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Hide typing indicator
            typingIndicator.classList.remove('active');
            
            // Show AI response
            appendMessage('assistant', data.content, data.id, userMessageId);
            
            // Update conversation list
            updateConversationList(messageText);
            
        } catch (error) {
            console.error('Error sending message:', error);
            typingIndicator.classList.remove('active');
            appendErrorMessage('Sorry, there was an error processing your request.');
        } finally {
            isProcessing = false;
        }
    }
    
    function appendMessage(sender, content, messageId, referenceId = null) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.dataset.id = messageId;
        
        if (referenceId) {
            messageDiv.dataset.referenceId = referenceId;
        }
        
        // Store message in history
        messageHistory.push({
            id: messageId,
            sender: sender,
            content: content,
            timestamp: new Date().toISOString(),
            reference_id: referenceId
        });
        
        // Create message content
        let formattedContent = content;
        
        // Format markdown content if it's from the assistant
        if (sender === 'assistant') {
            formattedContent = formatMarkdown(content);
        }
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-${sender === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">
                ${formattedContent}
                <div class="message-time">${formatTime(new Date())}</div>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to the new message
        scrollToBottom();
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
            
            // Start a new conversation
            currentConversationId = generateId();
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
    
    function startNewChat() {
        // Clear the chat interface
        while (chatMessages.children.length > 1) {
            chatMessages.removeChild(chatMessages.lastChild);
        }
        
        // Create new conversation ID
        currentConversationId = generateId();
        
        // Reset message history
        messageHistory = [];
        
        // Update conversation list
        updateConversationList('New Conversation');
        
        // Focus on input
        chatInput.focus();
    }
    
    async function fetchChatHistory() {
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
                
                // Group messages by pairs (user query and assistant response)
                for (let i = 0; i < data.length; i++) {
                    const message = data[i];
                    appendMessage(message.sender, message.content, message.id, message.reference_id);
                }
                
                // Update conversation list based on the first user message
                const firstUserMessage = data.find(msg => msg.sender === 'user');
                if (firstUserMessage) {
                    updateConversationList(firstUserMessage.content);
                }
            }
        } catch (error) {
            console.error('Error fetching chat history:', error);
        }
    }
    
    function updateConversationList(firstMessage) {
        // Check if we already have this conversation in the list
        const existingItem = document.querySelector(`.conversation-item[data-id="${currentConversationId}"]`);
        
        if (existingItem) {
            // Update existing item
            const titleElement = existingItem.querySelector('.conversation-title');
            if (titleElement) {
                titleElement.textContent = truncateText(firstMessage, 30);
            }
            
            const dateElement = existingItem.querySelector('.conversation-date');
            if (dateElement) {
                dateElement.textContent = formatTime(new Date());
            }
        } else {
            // Create new item
            const emptyState = conversationList.querySelector('.empty-state');
            if (emptyState) {
                emptyState.remove();
            }
            
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('conversation-item');
            itemDiv.dataset.id = currentConversationId;
            
            itemDiv.innerHTML = `
                <div class="conversation-title">${truncateText(firstMessage, 30)}</div>
                <div class="conversation-date">${formatTime(new Date())}</div>
            `;
            
            // Add click handler
            itemDiv.addEventListener('click', () => {
                // In a real app, this would load the conversation
                alert('In a fully implemented app, this would load the selected conversation.');
            });
            
            // Add to conversation list
            conversationList.insertBefore(itemDiv, conversationList.firstChild);
        }
    }
    
    // Utility functions
    function generateId() {
        return 'msg_' + Math.random().toString(36).substr(2, 9);
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