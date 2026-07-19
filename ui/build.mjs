import * as esbuild from 'esbuild';
import fs from 'node:fs';
fs.mkdirSync('dist', {recursive:true});
await esbuild.build({entryPoints:['src/main.tsx'],bundle:true,minify:false,sourcemap:true,outfile:'dist/app.js',loader:{'.tsx':'tsx','.ts':'ts'},jsx:'automatic'});
fs.copyFileSync('index.html','dist/index.html');
const morph = fs.readFileSync('index.html','utf8').replace('<div id="root"></div>','<div id="root"></div><script>location.hash="morph"</script>');
fs.writeFileSync('dist/morph.html', morph);
fs.copyFileSync('src/styles.css','dist/styles.css');
console.log('UI built: dist/');
