from project import create_app

application = create_app('development')

if __name__ == "__main__":
    create_app('development').run()