"""
Быстрый запуск pipeline через CLI:
  python run_analysis.py --email YOUR_EMAIL --password YOUR_PASSWORD
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Запуск анализа проекта через DeepSeek")
    parser.add_argument("--email", default=None, help="Email для DeepSeek")
    parser.add_argument("--password", default=None, help="Пароль для DeepSeek")
    args = parser.parse_args()

    if args.email:
        os.environ["DEEPSEEK_EMAIL"] = args.email
    if args.password:
        os.environ["DEEPSEEK_PASSWORD"] = args.password

    success = run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
