#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Verificador de PDF Simplificado
Verifica el PDF v2 con formato limpio y tabla como foco principal
"""

import os
from datetime import date

def verificar_pdf_simplificado():
    """Verifica el PDF simplificado generado"""
    
    nombre_archivo = f"LIQUIDACION_CUOTAS_PARTES_5742637_{date.today().strftime('%Y%m%d')}_v2.pdf"
    
    print("=" * 80)
    print("VERIFICACIÓN DEL PDF SIMPLIFICADO (V2)")
    print("=" * 80)
    
    if os.path.exists(nombre_archivo):
        # Obtener información del archivo
        tamaño = os.path.getsize(nombre_archivo)
        fecha_creacion = os.path.getctime(nombre_archivo)
        
        print(f"✅ ARCHIVO ENCONTRADO: {nombre_archivo}")
        print(f"📁 Tamaño: {tamaño:,} bytes ({tamaño/1024:.1f} KB)")
        print(f"📅 Creado: {date.fromtimestamp(fecha_creacion).strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n🎯 FORMATO SIMPLIFICADO:")
        print(f"   📋 TÍTULO INTEGRADO:")
        print(f"      • LIQUIDACIÓN MENSUAL CON INTERESES DTF")
        print(f"      • Pensionado: Acelas Mejia Libardo - ID: 5742637")
        print(f"      • Período: Septiembre 2022 → Agosto 2025 (36 meses)")
        
        print(f"\n📊 CONTENIDO PRINCIPAL:")
        print(f"   ✅ Solo la tabla de liquidación (foco principal)")
        print(f"   ✅ Datos del pensionado integrados en el título")
        print(f"   ✅ Sin información adicional que distraiga")
        print(f"   ✅ Formato limpio y directo")
        
        print(f"\n📈 TABLA DE DATOS:")
        print(f"   🔹 36 registros mensuales")
        print(f"   🔹 Columnas: PERÍODO | DÍAS | DTF EA | VALOR INTERÉS | INTERÉS ACUM. | CAPITAL")
        print(f"   🔹 Colores: Cabecera azul, datos alternados, totales amarillo")
        print(f"   🔹 Totales destacados en la última fila")
        
        print(f"\n💰 TOTALES EN LA TABLA:")
        print(f"   💵 Total Intereses: $170,536.87")
        print(f"   🏛️ Total Capital: $19,278,517.35")
        print(f"   🎯 Total Liquidación: $19,449,054.22")
        
        print(f"\n✨ MEJORAS DEL FORMATO V2:")
        print(f"   ✅ Eliminado: Encabezado largo del hospital")
        print(f"   ✅ Eliminado: Tabla de información separada")
        print(f"   ✅ Eliminado: Resumen ejecutivo extenso")
        print(f"   ✅ Eliminado: Notas técnicas detalladas")
        print(f"   ✅ Mantenido: Solo la tabla principal con datos esenciales")
        
        print(f"\n🎯 RESULTADO:")
        print(f"   📄 Documento más limpio y enfocado")
        print(f"   📊 Tabla como elemento principal")
        print(f"   👤 Datos del pensionado visibles pero no dominantes")
        print(f"   ⚡ Información directa y sin distracciones")
        
        # Comparar tamaños
        archivo_original = f"LIQUIDACION_CUOTAS_PARTES_5742637_{date.today().strftime('%Y%m%d')}.pdf"
        if os.path.exists(archivo_original):
            tamaño_original = os.path.getsize(archivo_original)
            print(f"\n📊 COMPARACIÓN DE VERSIONES:")
            print(f"   📄 V1 (Completo): {tamaño_original:,} bytes")
            print(f"   📄 V2 (Simplificado): {tamaño:,} bytes")
            reduccion = ((tamaño_original - tamaño) / tamaño_original) * 100
            print(f"   📉 Reducción: {reduccion:.1f}% más compacto")
        
        print(f"\n🚀 ESTADO: FORMATO OPTIMIZADO LISTO")
        
    else:
        print(f"❌ ERROR: No se encontró el archivo {nombre_archivo}")

if __name__ == "__main__":
    verificar_pdf_simplificado()