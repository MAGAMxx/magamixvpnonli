import subprocess
import sys
import threading

def run_main_bot():
    """Запуск основного бота"""
    subprocess.run([sys.executable, 'main_bot.py'])

def run_payment_bot():
    """Запуск платежного бота"""
    subprocess.run([sys.executable, 'payment_bot.py'])

def run_video_bot():
    """Запуск видео бота"""
    subprocess.run([sys.executable, 'video.py'])

if __name__ == '__main__':
    print("🚀 Запуск всех ботов...")
    print("📱 Основной бот запускается...")
    print("💳 Платежный бот запускается...")
    print("🎬 Видео бот запускается...")
    print()

    # Создаем потоки для каждого бота
    main_thread = threading.Thread(target=run_main_bot, daemon=True)
    payment_thread = threading.Thread(target=run_payment_bot, daemon=True)
    video_thread = threading.Thread(target=run_video_bot, daemon=True)

    # Запускаем все боты
    main_thread.start()
    payment_thread.start()
    video_thread.start()

    # Ждем завершения (бесконечно, пока боты работают)
    try:
        main_thread.join()
        payment_thread.join()
        video_thread.join()
    except KeyboardInterrupt:
        print("\n⏹ Остановка ботов...")
        sys.exit(0)