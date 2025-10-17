from app_initializer import AppInitializer


initializer = AppInitializer()
initializer.check_settings()
initializer.init_logger()
initializer.init_components()
initializer.run_indefinitely()
