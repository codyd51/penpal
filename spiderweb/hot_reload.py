import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from spiderweb import render_programs
from spiderweb.env import CONTENT_ROOT, CHAPTER_1_ROOT


class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        # print(event)
        print(f'Rendering markdown in response to {event}...')
        try:
            raise NotImplementedError()
            # render_markdown()
            render_programs()
        except Exception as e:
            print(f'Failed to render to markdown: {e}')
            raise


def main():
    event_handler = EventHandler()
    observer = Observer()
    observer.schedule(event_handler, CONTENT_ROOT.as_posix(), recursive=True)
    observer.schedule(event_handler, CHAPTER_1_ROOT.as_posix(), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    main()
