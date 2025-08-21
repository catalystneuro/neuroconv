/**
 * NeuroConv Assistant Chatbot
 * Opens the NWB Assistant chatbot in a persistent popup window
 * that maintains conversation state across documentation page navigation
 */

document.addEventListener('DOMContentLoaded', function() {
    // Create the toggle button only (no container or iframe needed for popup)
    const toggle = document.createElement('button');
    toggle.className = 'assistant-toggle';
    toggle.textContent = 'Open Assistant';

    // Append button to the body
    document.body.appendChild(toggle);

    // Track the popup window reference
    let chatbotWindow = null;

    // Add click event handler for the toggle button
    toggle.addEventListener('click', function() {
        // Check if window exists and is still open
        if (!chatbotWindow || chatbotWindow.closed) {
            // Open new popup window
            chatbotWindow = window.open(
                'https://magland.github.io/nwb-assistant/chat',
                'nwb-assistant', // Window name (ensures only one window)
                'width=500,height=700,scrollbars=yes,resizable=yes,location=no,menubar=no,toolbar=no,status=no'
            );

            // Update button text when window is opened
            if (chatbotWindow) {
                toggle.textContent = 'Focus Assistant';

                // Check if window gets closed and update button text
                const checkClosed = setInterval(function() {
                    if (chatbotWindow.closed) {
                        toggle.textContent = 'Open Assistant';
                        chatbotWindow = null;
                        clearInterval(checkClosed);
                    }
                }, 1000);
            }
        } else {
            // Window exists, just bring it to front
            chatbotWindow.focus();
        }
    });
});
