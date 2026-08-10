import time


def run():
    print("worker tick")


if __name__ == "__main__":
    while True:
        run()
        time.sleep(60)
