import sublime
from sublime_plugin import WindowCommand
from sublime_plugin import TextCommand
from sublime_plugin import EventListener
from subprocess import Popen, PIPE
from queue import Queue
from threading import Thread
import os
from functools import partial
import json

TSS_PATH =  os.path.join(os.path.dirname(__file__),'bin','tss.js')

# NOTE: we need to load the whole project! Search for every file in the whole project and load it in to the plugin, no?
# As soon as you load something like that... 
# Simple commands: mark errors in the current file


# STEPS: 
# (1) get tss into the repo
# (2) when first typescript loaded
    # (z) print a message, and never do it again
    # (a) load tss process
    # (b) feed it all the typescript info in the whole project

# oh, but it should be per-project, right? 
# depends on how it works :)

# ok, I know how this works, now I just need to figure out what the . 

# typescript service needs to be PER FILE

# OR, I could make a global. yeah.

# do we REALLY want to load it like that?
# well... I don't know. 
# I would rather it run reliably and slow

# PROBLEM: should use the typescript version of the local repository, no? (Almost impossible)
# just use the latest version. (Or publish version branches)

# Also: just have it load regularly, and ask the LOCAL version of the errors, no?
# so... I keep track of the project errors locally, totally parsed. 

class Error(object):
    file = None
    start = None
    end = None
    text = None
    phase = None
    category = None
    def __init__(self, dict):
        self.file = dict['file']
        self.start = ErrorPosition(dict['start'])
        self.end = ErrorPosition(dict['end'])
        self.text = dict['text']
        self.phase = dict['phase']
        self.category = dict['category']

class ErrorPosition(object):
    line = 0
    character = 0
    def __init__(self, dict):
        self.line = dict['line']
        self.character = dict['character']

class TypescriptService(object):
    
    process = None
    errors = []
    thread = None
    queue = None
    delegate = None
    loaded = False

    def reset(self):
        if (self.process): self.process.kill()
        if (self.queue): self.queue_empty()
        self.queue = Queue()
        self.thread = Thread(target=partial(self.queue_run))
        self.thread.daemon = True
        self.thread.start()

    # forces the loading of the typescript service at this point
    # unloads any project already loaded
    # if you can't find a project, just load every file, no?
    # if you CAN find a project, then use the active one?
    # only ever have one process
    def start(self, file_path):
        print("START: ", file_path)
        self.reset()
        kwargs = {}
        self.loaded = False
        self.process = Popen(["/usr/local/bin/node", TSS_PATH, file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)

    def queue_add(self, method):
        self.queue.put(method)
        
    def checkErrors(self):
        self.process_write(self.process, 'showErrors')
        infos = self.process_read(self.process)
        errors = list(map(lambda e: Error(e), infos))
        if (self.delegate):
            self.delegate.on_typescript_errors(errors)

    def queue_run(self):
        item = self.queue.get() # BLOCKING!
        print("RUN", item)
        item()
        self.queue.task_done()
        self.queue_run()

    # empties the whole queue
    def queue_empty(self):
        if (self.queue.empty()): return
        self.queue.get(False)
        self.queue_empty()

    def process_read(self, process):
        line = process.stdout.readline().decode('UTF-8')
        print("TSS: ", line)
        if line.startswith('"loaded'):
            self.loaded = True
            if (self.delegate):
                self.delegate.on_typescript_loaded()
            return self.process_read(process)
        else:
            return json.loads(line)

    def process_write(self, process, command):
        process.stdin.write(bytes(command+'\n','UTF-8'))



# loads the file in its own process
# does some AMAZING stuff
class TypescriptStartCommand(TextCommand):
    def run(self, edit):
        service.start(self.view.file_name())
        service.queue_add(service.checkErrors)
        service.delegate = self
        self.wait_for_load(service)

    def is_enabled(self):
        return isTypescript(self.view)

    def on_typescript_errors(self, errors):
        print("ERRORS!", errors)
        self.display_errors(errors)

    def on_typescript_loaded(self):
        print("LOADED!")


    def display_errors(self,errors):
        self.view.set_status("typescript", "Typescript [%s ERRORS]" % len(errors))

    def wait_for_load(self, service, i=0, dir=1):
        if (service.loaded):
            self.display_errors(service.errors)
        else:
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            self.view.set_status("typescript", 'Typescript Loading [%s=%s]' % (' ' *before, ' '*after))
            sublime.set_timeout(lambda: self.wait_for_load(service, i, dir), 100)




class TypescriptCheckCommand(TextCommand):
    def is_enabled(self):
        return isTypescript(self.view)

    def run(self, edit):
        print("Typescript check", edit)



class TypescriptEventListener(EventListener):

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        self.loaded = "loaded baby"
        print("on_activated_async", service, view.file_name())
        # if it is a typescript file, and we aren't loaded, run LOAD synchronously. Just burn through it fast

    def on_clone_async(self,view):
        print("on_clone_async")

    def init_view(self,view):
        print("init_view")

    def on_load_async(self, view):
        print("on_load_async")

    # # called on each character sent
    # def on_modified_async(self, view):
    #     print("on_modified_async")
        
    # # called a lot when selecting, AND each character
    # def on_selection_modified_async(self, view):
    #     print("on_selection_modified_async")        

    # def on_post_save_async(self,view):
    #     print("on_post_save_async")

    
        

    # def handle_timeout(self,view):
    #     self.pending = self.pending -1
    #     if self.pending == 0:
    #         TSS.errors(view)


    # def on_query_completions(self, view, prefix, locations):
    #     if is_ts(view):
    #         pos = view.sel()[0].begin()
    #         (line, col) = view.rowcol(pos)
    #         is_member = str(is_member_completion(view.substr(sublime.Region(view.line(pos-1).a, pos)))).lower()
    #         TSS.complete(view,line,col,is_member)

    #         return COMPLETION_LIST


    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        

service = TypescriptService()

def isTypescript(view=None):
    if view is None:
        view = sublime.active_window().active_view()
    return 'source.ts' in view.scope_name(0)

def plugin_loaded():
    settings = sublime.load_settings('typescript.sublime-settings')
    print("TS Loaded", settings)
    # sublime.set_timeout(lambda:init(sublime.active_window().active_view()), 300)
