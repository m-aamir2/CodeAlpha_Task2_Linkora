import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = path.join(projectRoot, 'backend')
const frontendDir = path.join(projectRoot, 'frontend')
const python = process.platform === 'win32'
  ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
  : path.join(backendDir, '.venv', 'bin', 'python')

if (!existsSync(python)) {
  console.error('Backend virtual environment is missing. Create it with:')
  if (process.platform === 'win32') {
    console.error('  py -m venv backend/.venv')
    console.error('  backend\\.venv\\Scripts\\pip install -r backend\\requirements.txt')
  } else {
    console.error('  python3 -m venv backend/.venv')
    console.error('  backend/.venv/bin/pip install -r backend/requirements.txt')
  }
  process.exit(1)
}

if (!existsSync(path.join(frontendDir, 'node_modules'))) {
  console.error('Frontend dependencies are missing. Install them with:')
  console.error('  npm install --prefix frontend')
  process.exit(1)
}

const services = []
let shuttingDown = false
let exitCode = 0
let forceExitTimer

function signalService(service, signal) {
  if (service.closed || !service.child.pid) return
  try {
    if (process.platform === 'win32') service.child.kill(signal)
    else process.kill(-service.child.pid, signal)
  } catch (error) {
    if (error.code !== 'ESRCH') console.error(`Could not stop ${service.name}: ${error.message}`)
  }
}

function finishIfStopped() {
  if (!shuttingDown || !services.every(service => service.closed)) return
  clearTimeout(forceExitTimer)
  process.exit(exitCode)
}

function stopAll(signal = 'SIGTERM') {
  for (const service of services) signalService(service, signal)
}

function shutdown(code = 0) {
  if (shuttingDown) {
    if (code !== 0) exitCode = code
    return
  }
  shuttingDown = true
  exitCode = code
  stopAll()
  forceExitTimer = setTimeout(() => {
    stopAll('SIGKILL')
    process.exit(exitCode)
  }, 5000)
  forceExitTimer.unref()
  finishIfStopped()
}

function startService(name, command, args, cwd) {
  console.log(`Starting ${name}…`)
  const child = spawn(command, args, {
    cwd,
    stdio: 'inherit',
    detached: process.platform !== 'win32',
    shell: process.platform === 'win32',
  })
  const service = { name, child, closed: false }
  services.push(service)

  child.once('error', error => {
    console.error(`${name} could not start: ${error.message}`)
    shutdown(1)
  })
  child.once('close', (code, signal) => {
    service.closed = true
    if (!shuttingDown) {
      console.error(`${name} stopped${signal ? ` (${signal})` : ` with exit code ${code}`}. Stopping the other server.`)
      shutdown(code || 1)
    }
    finishIfStopped()
  })
}

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
console.log('Linkora development servers')
console.log('Frontend: http://localhost:5180')
console.log('Backend:  http://127.0.0.1:8001/api/')
console.log('Press Ctrl+C to stop both servers.\n')

startService('Django', python, ['manage.py', 'runserver'], backendDir)
startService('Vite', npm, ['run', 'dev'], frontendDir)

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
