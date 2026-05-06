import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function AvatarCanvas({ active = false }) {
  const mountRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0b0f18)

    const camera = new THREE.PerspectiveCamera(35, mount.clientWidth / mount.clientHeight, 0.1, 100)
    camera.position.set(0, 0, 5.5)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    const ambient = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambient)
    const key = new THREE.DirectionalLight(0x8b9dff, 1.2)
    key.position.set(4, 4, 4)
    scene.add(key)

    const shellGeom = new THREE.SphereGeometry(1.5, 64, 64)
    const shellMat = new THREE.MeshPhysicalMaterial({
      color: 0x4f67b8,
      roughness: 0.32,
      metalness: 0.15,
      transmission: 0.06,
      clearcoat: 0.55,
      clearcoatRoughness: 0.2,
      emissive: 0x1f2e59,
      emissiveIntensity: 0.35,
    })
    const shell = new THREE.Mesh(shellGeom, shellMat)
    scene.add(shell)

    const coreGeom = new THREE.SphereGeometry(0.72, 48, 48)
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0x6f82da,
      emissive: 0x8ba0ff,
      emissiveIntensity: 0.85,
      roughness: 0.2,
      metalness: 0.12,
    })
    const core = new THREE.Mesh(coreGeom, coreMat)
    scene.add(core)

    const ringGeom = new THREE.TorusGeometry(2.05, 0.03, 16, 220)
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xa78bfa, transparent: true, opacity: 0.45 })
    const ring = new THREE.Mesh(ringGeom, ringMat)
    ring.rotation.x = Math.PI * 0.6
    scene.add(ring)

    const clock = new THREE.Clock()
    let raf = 0

    const render = () => {
      const t = clock.getElapsedTime()
      shell.rotation.y += 0.0022
      core.rotation.y -= 0.003
      ring.rotation.z += 0.004

      const pulse = active ? 0.12 : 0.05
      const targetScale = 1 + Math.sin(t * (active ? 3.8 : 1.5)) * pulse
      core.scale.setScalar(targetScale)
      coreMat.emissiveIntensity = active ? 1.2 : 0.8
      ringMat.opacity = active ? 0.8 : 0.45

      renderer.render(scene, camera)
      raf = window.requestAnimationFrame(render)
    }
    render()

    const onResize = () => {
      if (!mount) return
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      window.cancelAnimationFrame(raf)
      shellGeom.dispose()
      shellMat.dispose()
      coreGeom.dispose()
      coreMat.dispose()
      ringGeom.dispose()
      ringMat.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [active])

  return <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
}

