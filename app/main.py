def welcome(name: str = "用户") -> str:
    return f"欢迎来到 Sports Agent，{name}！"


if __name__ == "__main__":
    print(welcome())
