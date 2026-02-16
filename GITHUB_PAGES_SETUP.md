# GitHub Pages Setup Instructions

This repository is configured to be deployed via GitHub Pages. The webpage files (`index.html`, `app.js`, `style.css`) are located in the root directory.

## Enabling GitHub Pages

To make the webpage accessible at `https://cgutt-hub.github.io/paperFinder/`:

1. Go to your repository on GitHub: `https://github.com/CGutt-hub/paperFinder`

2. Click on **Settings** (⚙️ icon) in the top menu

3. In the left sidebar, click on **Pages** (under "Code and automation")

4. Under **Source**, select:
   - **Source**: Deploy from a branch
   - **Branch**: Select `main` (or whichever branch contains these files)
   - **Folder**: Select `/ (root)`

5. Click **Save**

6. Wait a few minutes for GitHub to build and deploy your site

7. The page will be available at: `https://cgutt-hub.github.io/paperFinder/`

## Files Required for GitHub Pages

The following files are required and are already in the root directory:

- ✅ `index.html` - Main HTML page
- ✅ `app.js` - JavaScript application logic
- ✅ `style.css` - Custom styles for this tool
- ✅ `.nojekyll` - Tells GitHub Pages not to process files with Jekyll

## External Dependencies

The webpage loads shared components from the `5ha99y` repository:
- Header and footer components
- Base theme CSS

Make sure the `5ha99y` repository is also deployed for full functionality.

## Local Testing

To test the webpage locally:

```bash
# Using Python's built-in HTTP server
python -m http.server 8000

# Or using Node.js http-server
npx http-server -p 8000
```

Then visit `http://localhost:8000` in your browser.
