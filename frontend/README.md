# CodeAgent Frontend

A beautiful, modern web interface for the CodeAgent API.

## Design Aesthetic

The frontend uses a **Dark Cyberpunk IDE** theme with:
- **Typography**: JetBrains Mono for code, Orbitron for headings, Rajdhani for body text
- **Color Palette**: Deep space blues, neon cyan accents, purple gradients
- **Animations**: Smooth transitions, glowing effects, subtle motion
- **Layout**: Responsive design optimized for desktop and mobile

## Features

- **Chat Interface**: Real-time code Q&A with typing indicators and source references
- **Repository Management**: Add, view, and switch between code repositories
- **Session History**: View and resume previous conversations
- **Health Status**: Live connection status indicator
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile

## Quick Start

1. **Start the API Server**:
   ```bash
   cd /d/code/CodeAgent
   python -m src.api.main
   ```

2. **Open the Frontend**:
   Simply open `frontend/index.html` in your browser, or use a local server:
   ```bash
   cd frontend
   python -m http.server 8080
   ```
   Then visit: `http://localhost:8080`

## Usage

### Adding a Repository

1. Click "Add Repository" in the sidebar
2. Fill in the repository details:
   - **Repository ID**: Unique identifier (lowercase letters, numbers, hyphens)
   - **Name**: Display name
   - **Path**: Absolute path to the repository on disk
3. Click "Add Repository"

### Chatting About Code

1. Select a repository from the sidebar
2. Type your question in the chat input
3. Press Enter or click the send button
4. View the AI's response with source file references

### Session Management

- Sessions are automatically created for each repository
- View session history in the sidebar
- Click on a session to view previous conversations

## API Connection

The frontend connects to the CodeAgent API at `http://localhost:8000`.

To change the API endpoint, edit `frontend/app.js`:
```javascript
const API_BASE_URL = 'http://your-api-url:port/api/v1';
```

## Browser Compatibility

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

## Customization

### Colors

Edit the CSS variables in `styles.css`:
```css
:root {
    --accent-primary: #06b6d4;  /* Cyan */
    --accent-secondary: #8b5cf6; /* Purple */
    /* ... more colors */
}
```

### Fonts

The frontend uses Google Fonts. To change fonts:
1. Update the Google Fonts link in `index.html`
2. Update the CSS variables in `styles.css`

### Layout

The sidebar width and other layout parameters are defined in CSS variables:
```css
.sidebar {
    width: 320px; /* Adjust sidebar width */
}
```

## File Structure

```
frontend/
├── index.html      # Main HTML structure
├── styles.css      # Cyberpunk-themed styling
├── app.js         # Application logic and API client
└── README.md      # This file
```

## Development Tips

- **Hot Reload**: Use `python -m http.server` for instant updates when editing files
- **Console Logging**: Check browser console for API errors and debug info
- **Network Tab**: Monitor API requests in browser DevTools

## Troubleshooting

### "Connecting..." status persists

- Verify the API server is running at `http://localhost:8000`
- Check browser console for CORS errors
- Ensure the API is not blocked by a firewall

### Can't add repository

- Verify the repository path is absolute and exists on disk
- Check API server logs for errors
- Ensure repository ID uses only lowercase letters, numbers, and hyphens

### Chat not working

- Verify a repository is selected
- Check the API server health endpoint: `http://localhost:8000/health`
- Ensure the repository has been indexed (check API logs)

## Design Decisions

### Why Dark Theme?

Dark themes reduce eye fatigue during extended coding sessions and provide higher contrast for code syntax highlighting.

### Why These Fonts?

- **Orbitron**: Futuristic, tech-focused display font
- **JetBrains Mono**: Professional monospace font optimized for code
- **Rajdhani**: Clean, legible body font with excellent readability

### Why Vanilla JS?

No framework required means:
- Zero dependencies
- Fast load times
- Easy to understand and modify
- Works in any browser without build tools

## Future Enhancements

- Syntax highlighting for code blocks
- File tree viewer
- Export chat history
- Dark/light theme toggle
- Multi-line code editor
- Real-time collaboration

## License

Same as parent CodeAgent project.
