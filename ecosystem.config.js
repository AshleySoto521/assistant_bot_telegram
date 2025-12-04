module.exports = {
  apps : [{
    name   : "bot-telegram",
    script : "./main.py",
    interpreter: "python", // O la ruta absoluta si la usaste antes
    interpreter_args: "-u",
    
    // --- AQUÍ ESTÁ LA SOLUCIÓN ---
    watch: false, // Desactivamos el reinicio automático por cambios
    
    // Por seguridad, si alguna vez activas el watch, le decimos que ignore la DB
    ignore_watch: ["*.db", "*.db-journal", "__pycache__", "*.log"],
    
    env: {
      PYTHONIOENCODING: "utf-8"
    }
  }]
}