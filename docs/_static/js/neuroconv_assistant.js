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

    // Function to get optimal popup size and position for multi-monitor setups
    const getOptimalPopupSize = () => {
        // Get current window position to determine which screen we're on
        const currentLeft = window.screenX || window.screenLeft || 0;
        const currentTop = window.screenY || window.screenTop || 0;
        const currentWidth = window.outerWidth;

        // Determine popup size based on screen size
        const screenWidth = window.screen.width;
        let width, height;

        if (screenWidth <= 768) {
            // Mobile: smaller popup
            width = Math.min(400, screenWidth - 40);
            height = Math.min(600, window.screen.height - 100);
        } else if (screenWidth <= 1024) {
            // Tablet: medium popup
            width = 450;
            height = 650;
        } else if (screenWidth <= 1440) {
            // Desktop: standard popup
            width = 500;
            height = 700;
        } else {
            // Large desktop: bigger popup
            width = 600;
            height = 800;
        }

        // Position popup near current window (same monitor)
        // Try to place it to the right of current window
        let left = currentLeft + currentWidth + 20; // 20px gap from browser window
        let top = currentTop + 50; // Small offset from top of browser

        // If popup would extend beyond screen, center it instead
        const maxLeft = currentLeft + screenWidth - width;
        if (left > maxLeft) {
            left = currentLeft + Math.round((screenWidth - width) / 2);
        }

        // Ensure popup doesn't go below screen
        const maxTop = window.screen.height - height - 50;
        if (top > maxTop) {
            top = Math.max(50, Math.round((window.screen.height - height) / 2));
        }

        return { width, height, left, top };
    };

    // Add click event handler for the toggle button
    toggle.addEventListener('click', function() {
        // Check if window exists and is still open
        if (!chatbotWindow || chatbotWindow.closed) {
            // Get optimal size for current screen
            const { width, height, left, top } = getOptimalPopupSize();

            // Open new popup window with responsive sizing
            chatbotWindow = window.open(
                'https://magland.github.io/nwb-assistant/chat',
                'nwb-assistant', // Window name (ensures only one window)
                `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes,location=no,menubar=no,toolbar=no,status=no`
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
