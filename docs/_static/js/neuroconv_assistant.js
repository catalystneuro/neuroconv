/**
 * NeuroConv Assistant Chatbot
 * Dynamically injects the NWB Assistant chatbot into every documentation page
 */

document.addEventListener('DOMContentLoaded', function() {
    // Create the assistant container
    const container = document.createElement('div');
    container.className = 'assistant-container';

    // Create the iframe for the chatbot
    const iframe = document.createElement('iframe');
    iframe.className = 'assistant-iframe';
    container.appendChild(iframe);

    // Create the toggle button
    const toggle = document.createElement('button');
    toggle.className = 'assistant-toggle';
    toggle.textContent = 'Open Assistant';

    // Append elements to the body
    document.body.appendChild(container);
    document.body.appendChild(toggle);

    // Track whether iframe has been loaded
    let iframeLoaded = false;

    // Add click event handler for the toggle button
    toggle.addEventListener('click', function() {
        const isShowing = container.classList.toggle('show');

        // Load iframe content only when first opened for performance
        if (isShowing && !iframeLoaded) {
            iframe.src = 'https://magland.github.io/nwb-assistant/chat';
            iframeLoaded = true;
        }
    });
});
