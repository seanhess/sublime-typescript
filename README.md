Sublime-Typescript
==================

THIS PLUGIN IS NOT MAINTAINED. I recommend using https://github.com/Railk/T3S

A Sublime Text plugin for the Typescript language.

Features
--------

- Inline error highlighting as you type
- Autocompletion

Installation
------------

Install [Node.JS](http://nodejs.org/)

Clone the repository in your sublime "Packages" directory. 

~~~sh
cd ~/Library/Application Support/Sublime Text 3/Packages
git clone https://github.com/seanhess/sublime-typescript
~~~

Make sure you set `auto_complete: true`, either in your global settings or typescript.sublime-settings

Issues and Questions
--------------------

- Autocomplete is finicky if set to false
- It does not follow references except on the first file, run the `Typescript: Start Here` command to reload on the current file 
