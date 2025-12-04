module.exports = {
  apps : [{
    name   : "bot-telegram",
    script : "./main.py",
    interpreter: "python",
    interpreter_args: "-u",
    watch: false, // Desactivamos el reinicio automático por cambios
    
    // Por seguridad, si alguna vez activas el watch, le decimos que ignore la DB
    ignore_watch: ["*.db", "*.db-journal", "__pycache__", "*.log"],
    
    env: {
      PYTHONIOENCODING: "utf-8"
    }
  }]
}