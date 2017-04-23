from project import create_app

application = create_app('production')

if __name__ == "__main__":
    create_app('production').run()