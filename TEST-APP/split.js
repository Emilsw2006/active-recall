const fs = require('fs');
const path = require('path');

const p = path.join('c:/Users/Emil/Desktop/ACTIVE RECALL/TEST-APP', 'index.html');
const html = fs.readFileSync(p, 'utf-8');

const styleStart = html.indexOf('<style>') + '<style>'.length;
const styleEnd = html.indexOf('</style>');
const css = html.substring(styleStart, styleEnd).trim();

const scriptStart = html.indexOf('<script>') + '<script>'.length;
const scriptEnd = html.indexOf('</script>', scriptStart);
const js = html.substring(scriptStart, scriptEnd).trim();

const htmlNew = html.substring(0, html.indexOf('<style>')) + 
  '<link rel="stylesheet" href="style.css" />\n' + 
  html.substring(styleEnd + '</style>'.length, html.indexOf('<script>')) + 
  '<script src="app.js"></script>\n' + 
  html.substring(scriptEnd + '</script>'.length);

fs.writeFileSync(path.join('c:/Users/Emil/Desktop/ACTIVE RECALL/TEST-APP', 'style.css'), css, 'utf-8');
fs.writeFileSync(path.join('c:/Users/Emil/Desktop/ACTIVE RECALL/TEST-APP', 'app.js'), js, 'utf-8');
fs.writeFileSync(p, htmlNew, 'utf-8');

console.log('Split successful');
