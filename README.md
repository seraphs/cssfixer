cssfixer
========

part 1: css fixer for android

1) The fixing of separate css files is processed before they are available to the browser

2) In browser.js, a function named 'TracingListener' is added to get and process css files' content

3) Put all js files into gecko/mobile/android/chrome/content 

4) Put jar.mn to gecko/mobile/android/chrome/ 

5) Build a apk to test it


part 2: how to repack fennec after modifing *.js

1) open repack_config.py, and change value of 'HOME' to your working directory

2) run ./repack.sh

3) the new apk lies in ./output

BTW: 

1) you can modify all of the three files:browser.js, bootstrap.js and css-browserside.js
