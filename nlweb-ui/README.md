# NLWeb Chat UI

A browser-based chat interface that connects to the NLWeb HTTP endpoint, displays streaming results, and saves conversations to localStorage.

## Features

- ✅ **Streaming responses** via Server-Sent Events (SSE)
- ✅ **Conversation history** saved in localStorage
- ✅ **Sidebar navigation** with all past conversations
- ✅ **Two-stage input flow**: Center input for first query, bottom input for follow-ups
- ✅ **Site filtering**: Optional site parameter for each query
- ✅ **Resource cards**: Rich display of Schema.org data with images
- ✅ **Responsive design**: Works on desktop, tablet, and mobile
- ✅ **Mobile sidebar**: Slide-in navigation with overlay

## Quick Start

1. Open `index.html` in a web browser
2. Click the 💬 button to open the chat
3. Enter your question and optionally a site filter
4. See results stream in real-time
5. Continue the conversation with follow-up questions

## Files

```
nlweb-ui/
├── index.html          # Main HTML structure
├── nlweb-chat.js       # JavaScript application logic
└── nlweb-chat.css      # Stylesheet and responsive design
```

## Configuration

Edit the `NLWebChat` constructor in `nlweb-chat.js`:

```javascript
const chat = new NLWebChat({
    baseUrl: 'https://nlw.azurewebsites.net',  // NLWeb endpoint
    defaultSite: 'all',                         // Default site filter
    maxResults: 50                              // Max results per query
});
```

## Usage Patterns

### Initial Query
- Input box appears centered when no messages exist
- Enter query and optional site filter
- Hit Enter or click Send button

### Follow-up Queries
- After first query, input moves to bottom
- Messages appear in conversation area above
- Site filter persists from initial query
- Continue conversation naturally

### Conversation Management
- **New Chat**: Click + button in sidebar
- **Load Conversation**: Click any conversation in sidebar
- **Auto-save**: All conversations saved automatically
- **Persistent**: Data survives page refreshes

### Mobile Experience
- Tap ☰ to open sidebar
- Tap overlay or conversation to close
- Swipe-friendly interface
- No zoom on input fields (iOS)

## Response Format

The UI handles two types of content from NLWeb:

### Text Content
```json
{
    "type": "text",
    "text": "Description or summary text"
}
```

Renders as a simple paragraph with blue left border.

### Resource Content
```json
{
    "type": "resource",
    "resource": {
        "data": {
            "@type": "Item",
            "url": "https://example.com",
            "name": "Title",
            "site": "example.com",
            "description": "Description",
            "@graph": [/* Schema.org structured data */]
        }
    }
}
```

Renders as a card with:
- Image (if available in Schema.org data)
- Title (clickable link)
- Description
- Site badge

## Schema.org Data Extraction

The UI intelligently extracts data from Schema.org `@graph`:

- **Recipe**: `@type: Recipe` → name, image
- **Article**: `@type: Article` → headline
- **WebPage**: `@type: WebPage` → name
- **ImageObject**: `@type: ImageObject` → url
- **Thumbnails**: thumbnailUrl property

## Browser Compatibility

- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile Safari (iOS)
- ✅ Chrome Mobile (Android)

Requires:
- ES6+ JavaScript support
- EventSource API (SSE)
- localStorage API
- CSS Grid/Flexbox

## localStorage Structure

### Conversations Storage
```javascript
{
    "conversation_id_1": {
        "id": "1234567890",
        "title": "First user query...",
        "createdAt": "2025-11-15T00:00:00.000Z",
        "messages": [
            {
                "id": "msg_1",
                "role": "user",
                "content": "query text",
                "metadata": {"site": "example.com"},
                "timestamp": "2025-11-15T00:00:00.000Z"
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "content": [/* array of content items */],
                "timestamp": "2025-11-15T00:00:01.000Z"
            }
        ]
    }
}
```

### Storage Keys
- `nlweb_conversations`: All conversations object
- `nlweb_current`: ID of current/last conversation

## Deployment Options

### 1. Static Hosting
Upload files to any static host:
- GitHub Pages
- Netlify
- Vercel
- AWS S3 + CloudFront
- Azure Static Web Apps

### 2. Embedded Widget
Include in existing pages:
```html
<link rel="stylesheet" href="nlweb-chat.css">
<script src="nlweb-chat.js"></script>
```

### 3. Standalone Application
Open `index.html` directly in browser (file:// protocol works)

## Customization

### Styling
Edit `nlweb-chat.css` to customize:
- Colors (search for `#007bff` for primary color)
- Fonts (currently using system font stack)
- Spacing and layout
- Animation timing

### Behavior
Edit `nlweb-chat.js` to modify:
- SSE endpoint URL
- Default parameters
- Content rendering
- Storage logic

## Development

### Testing Locally
```bash
# Simple HTTP server
python3 -m http.server 8000

# Or Node.js
npx http-server
```

Then open: `http://localhost:8000`

### Debugging
- Open browser DevTools console
- Check Network tab for SSE connections
- Inspect localStorage in Application tab
- Monitor stream messages in console

## API Integration

The UI expects NLWeb HTTP endpoint responses in this format:

### Streaming (SSE)
```
data: {"_meta": {"version": "0.5"}}

data: {"content": [{"type": "text", "text": "..."}]}

data: {"content": [{"type": "resource", "resource": {...}}]}
```

### HTTP Query Parameters
- `query` (required): Search query text
- `site` (optional): Site filter (default: "all")
- `num_results` (optional): Max results (default: 50)
- `streaming` (required): Set to "true" for SSE

## Troubleshooting

### No responses appearing
- Check browser console for errors
- Verify NLWeb endpoint is accessible
- Check CORS headers on server
- Confirm EventSource connection in Network tab

### Conversations not saving
- Check localStorage quota (usually 5-10MB)
- Verify no Private/Incognito mode
- Clear localStorage if corrupted: `localStorage.clear()`

### Mobile sidebar not working
- Check viewport meta tag is present
- Verify CSS media queries loading
- Test touch events in DevTools mobile mode

### Images not loading
- Check Schema.org data structure
- Verify image URLs are valid
- Look for CORS issues with images
- Check `onerror` handler on img tags

## Performance

- **Lazy loading**: Images load on-demand
- **Efficient storage**: Only metadata stored, not full HTML
- **Stream processing**: Content renders progressively
- **Auto-scroll**: Smooth scrolling during streaming

## Security

- **XSS Protection**: All user content escaped via DOM APIs
- **External Links**: Use `rel="noopener"` for security
- **HTTPS**: Works over HTTPS or HTTP (EventSource supports both)
- **No eval()**: No dynamic code execution

## License

MIT License - see LICENSE file for details.

## Support

For issues or questions:
- Open issue on GitHub
- Check NLWeb documentation
- Review browser console logs
