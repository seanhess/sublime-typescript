import sublime
from sublime_plugin import WindowCommand
from sublime_plugin import TextCommand
from sublime_plugin import EventListener
from subprocess import Popen, PIPE
from queue import Queue
from threading import Thread
import time
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



class TypescriptService(object):
    
    process = None
    errors = []
    queue = None
    delegate = None
    loaded = False
    reader = None
    writer = None

    root_view = None

    # you CAN'T break this down. Keep it open always
    # If you want to add another file, do something different.

    # naw, this is a bad idea

    def is_initialized(self):
        return self.process != None

    def initialize(self, root_file_path):
        # can only initialize once
        print("initialize", os.path.join(os.path.dirname(__file__),'nothing.ts'))

        self.loaded = False        

        kwargs = {}
        self.process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.writer = ToolsWriter(self.process.stdin)
        self.writer.start()

        # but it's still kind of like... subscribe to the NEXT one
        self.reader = ToolsReader(self.process.stdout)
        self.reader.next_message(self.on_loaded)
        self.reader.start()

    # Only allow you to start once for now?
    def start(self, file_path):
        return
        self.initialize(file_path)


    def on_loaded(self, message):
        self.loaded = True
        self.check_errors()
        if (self.delegate):
            self.delegate.on_typescript_loaded()

    def check_errors(self):
        self.writer.add('showErrors')
        self.reader.next_data(self.on_errors)

    def on_errors(self, error_infos):
        print("infos", error_infos)
        errors = list(map(lambda e: Error(e), error_infos))
        if (self.delegate):
            self.delegate.on_typescript_errors(errors)


    def add_file(self, view):
        print("add_file", view.file_name())
        if (self.is_initialized()):
            self.update_file(view)
        else:
            self.initialize(view.file_name())

    # automatically runs checkerrors
    def update_file(self, view):
        (lineCount, col) = view.rowcol(view.size())
        content = view.substr(sublime.Region(0, view.size()))
        self.writer.add('update nocheck {0} {1}'.format(str(lineCount+1),view.file_name().replace('\\','/')))
        self.writer.add(content)
        self.reader.next_message(lambda m: self.check_errors())

        # Ok, so you need to WAIT, until the last command is finished to do another

    #     line = self.process_read(self.process)
    #     print("UPDATED FILE", line)

    #     # self.process_read(self.process)
    #     # self.check_errors()

    # def queue_is_running(self):
    #     return self.currentAction

    # def queue_run(self):
    #     # so if it is stopped
    #     # if self.queue_is_running(): return
    #     self.thread = Thread(target=partial(self.queue_next))
    #     self.thread.daemon = True
    #     self.thread.start()

    # # don't block, just start and stop depending on what is happening
    # # keep running items until it is empty again, then stop
    # def queue_next(self):
    #     # if self.queue.empty(): return
    #     item = self.queue.get() # BLOCKING
    #     print("RUN", item)
    #     item()
    #     self.queue.task_done()
    #     self.queue_next()

    # # empties the whole queue
    # def queue_empty(self):
    #     if (self.queue.empty()): return
    #     self.queue.get(False)
    #     self.queue_empty()

    # def process_read(self, process):
    #     line = process.stdout.readline().decode('UTF-8')
    #     print("<<< ", line)
    #     if line.startswith('"loaded'):
    #         self.loaded = True
    #         if (self.delegate):
    #             self.delegate.on_typescript_loaded()
    #         return self.process_read(process)
    #     # elif line.startswith('"updated'):
    #     #     return self.process_read(process)
    #     else:
    #         return json.loads(line)

    # def process_write(self, process, command):
    #     print(">>> " + command)
    #     process.stdin.write(bytes(command+'\n','UTF-8'))







class ToolsWriter(Thread):

    queue = Queue()

    def __init__(self, stdin):
        Thread.__init__(self)
        self.stdin = stdin        
        self.daemon = True

    def add(self, message):
        self.queue.put(message)

    def run(self):
        for command in iter(self.queue.get, None):
            print("TOOLS (write)", command[:100])
            self.stdin.write(bytes(command+'\n','UTF-8'))
        self.stdin.close()

class ToolsReader(Thread):

    on_data = None
    on_message = None

    def __init__(self, stdout):
        Thread.__init__(self)
        self.stdout = stdout
        self.daemon = True

    def next_data(self, handler):
        self.on_data = handler

    def next_message(self, handler):
        self.on_message = handler

    def run(self):
        for line in iter(self.stdout.readline, b''):
            line = line.decode('UTF-8')
            print("TOOLS (read)", line)            
            data = json.loads(line)
            if line.startswith('"'):
                if self.on_message:
                    self.on_message(data)
                    self.on_message = None    
                else:
                    print(" -- no handler")

            elif self.on_data:
                self.on_data(data)
                self.on_data = None

        self.stdout.close()




# I need a new model for this!!!
# 1. update, code
# 2. wait for updated message
# 3. 

# loads the file in its own process
# does some AMAZING stuff
class TypescriptStartCommand(TextCommand):
    def run(self, edit):
        service.start(self.view.file_name())
        service.delegate = self
        self.wait_for_load(service)

    def is_enabled(self):
        return isTypescript(self.view)

    def on_typescript_errors(self, errors):
        self.display_errors(errors)

    def on_typescript_loaded(self):
        service.check_errors()        

    def display_errors(self,errors):
        self.view.set_status("typescript", "Typescript [%s ERRORS]" % len(errors))
        render_errors(self.view, errors)

    def wait_for_load(self, service, i=0, dir=1):
        # self.display_errors(service.errors)
        if not service.loaded:
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            self.view.set_status("typescript", 'Typescript Loading [%s=%s]' % (' ' *before, ' '*after))
            sublime.set_timeout(lambda: self.wait_for_load(service, i, dir), 100)




def render_errors(view, errors):
    file = view.file_name()
    print("RENDER_ERRORS", len(errors), file)
    matching_errors = [e for e in errors if e.file == file]
    regions = list(map(lambda e: error_region(view, e), matching_errors))
    view.add_regions('typescript-error', regions, 'invalid', 'cross', sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE)


def error_region(view, error):
    a = view.text_point(error.start.line-1, error.start.character-1)
    b = view.text_point(error.end.line-1, error.end.character-1)
    return sublime.Region(a, b)




class TypescriptEventListener(EventListener):

    currentView = None

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        print("on_activated_async", service, view.file_name())
        if isTypescript(view): 
            self.currentView = view
            service.delegate = self
            service.add_file(view)
        else:
            self.currentView = None
        # if it is a typescript file, and we aren't loaded, run LOAD synchronously. Just burn through it fast

    def on_clone_async(self,view):
        print("on_clone_async")

    def init_view(self,view):
        print("init_view")

    def on_load_async(self, view):
        print("on_load_async")


    def on_typescript_loaded(self):
        print("loaded")

    # # called on each character sent
    def on_modified_async(self, view):
        # print("ON MODIFIED")
        if (isTypescript(view)):
            print("gogogo", view.file_name())
            self.currentView = view
            service.update_file(view)
            service.delegate = self
        # print("on_modified_async")

    def on_typescript_errors(self, errors):
        if self.currentView:
            render_errors(self.currentView, errors)
        
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
