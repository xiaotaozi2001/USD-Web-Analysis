import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'

interface AnalysisResult {
  filename: string
  analysis: {
    success: boolean
    references: Array<{
      path: string
      type: string
      prim_path: string
    }>
    textures: Array<{
      path: string
      shader: string
      input: string
      type: string
    }>
    error?: string
  }
}

export default function SimplePage() {
  const [results, setResults] = useState<AnalysisResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => /\.(usd|usda|usdc)$/i.test(file.name))
    if (validFiles.length === 0) {
      setError('请上传 .usd, .usda 或 .usdc 文件')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', validFiles[0])

      const response = await axios.post('http://localhost:63080/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setResults([response.data])
    } catch (error: any) {
      setError(error.response?.data?.detail || '分析过程中出现错误')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.usd', '.usda', '.usdc']
    },
    multiple: false
  })

  const containerStyle = {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '2rem 1rem',
  }

  const titleStyle = {
    fontSize: '1.875rem',
    fontWeight: 'bold',
    marginBottom: '2rem',
    textAlign: 'center' as const,
  }

  const dropzoneStyle = {
    border: '2px dashed rgba(255, 255, 255, 0.2)',
    borderRadius: '1rem',
    padding: '2rem',
    textAlign: 'center' as const,
    transition: 'all 0.3s ease',
    background: 'rgba(255, 255, 255, 0.05)',
    cursor: 'pointer',
  }

  const dropzoneActiveStyle = {
    ...dropzoneStyle,
    borderColor: '#60A5FA',
    background: 'rgba(96, 165, 250, 0.1)',
  }

  const errorStyle = {
    background: 'rgba(239, 68, 68, 0.1)',
    borderLeft: '4px solid #EF4444',
    padding: '1rem',
    borderRadius: '0.5rem',
    margin: '1rem 0',
    color: '#FCA5A5',
  }

  const loadingStyle = {
    marginTop: '2rem',
    textAlign: 'center' as const,
  }

  const spinnerStyle = {
    border: '3px solid rgba(255, 255, 255, 0.1)',
    borderTop: '3px solid #60A5FA',
    borderRadius: '50%',
    width: '24px',
    height: '24px',
    animation: 'spin 1s linear infinite',
    margin: '0 auto 1rem',
  }

  const resultContainerStyle = {
    marginTop: '2rem',
  }

  const resultTitleStyle = {
    fontSize: '1.5rem',
    fontWeight: 600,
    marginBottom: '1rem',
  }

  const statsContainerStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '1rem',
    margin: '1rem 0',
  }

  const statCardStyle = {
    background: 'rgba(255, 255, 255, 0.05)',
    borderRadius: '0.5rem',
    padding: '1rem',
    textAlign: 'center' as const,
  }

  const statValueStyle = {
    fontSize: '2rem',
    fontWeight: 'bold',
    color: '#60A5FA',
  }

  const statLabelStyle = {
    fontSize: '0.875rem',
    color: 'rgba(255, 255, 255, 0.7)',
  }

  const sectionStyle = {
    marginTop: '1.5rem',
  }

  const sectionTitleStyle = {
    fontSize: '1.25rem',
    fontWeight: 600,
    marginBottom: '0.75rem',
  }

  const itemStyle = {
    background: 'rgba(255, 255, 255, 0.05)',
    borderRadius: '0.5rem',
    padding: '1rem',
    margin: '0.5rem 0',
    transition: 'all 0.3s ease',
  }

  const itemPathStyle = {
    fontWeight: 500,
    marginBottom: '0.25rem',
  }

  const itemDetailStyle = {
    fontSize: '0.875rem',
    color: 'rgba(156, 163, 175, 1)',
  }

  return (
    <main style={containerStyle}>
      <h1 style={titleStyle}>USD Asset Analysis</h1>

      <div
        {...getRootProps()}
        style={isDragActive ? dropzoneActiveStyle : dropzoneStyle}
      >
        <input {...getInputProps()} />
        <p style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>将USD文件拖放到这里，或点击选择文件</p>
        <p style={{ fontSize: '0.875rem', color: 'rgba(156, 163, 175, 1)' }}>支持 usd, usda 和 usdc 文件</p>
      </div>

      {error && (
        <div style={errorStyle}>
          <p>{error}</p>
        </div>
      )}

      {isLoading && (
        <div style={loadingStyle}>
          <div style={spinnerStyle}></div>
          <p>正在分析文件...</p>
        </div>
      )}

      {results.map((result, index) => (
        <div key={`${result.filename}-${index}`} style={resultContainerStyle}>
          <h2 style={resultTitleStyle}>{result.filename}</h2>

          {result.analysis.success ? (
            <>
              <div style={statsContainerStyle}>
                <div style={statCardStyle}>
                  <div style={statValueStyle}>{result.analysis.references.length}</div>
                  <div style={statLabelStyle}>引用数量</div>
                </div>
                <div style={statCardStyle}>
                  <div style={statValueStyle}>{result.analysis.textures.length}</div>
                  <div style={statLabelStyle}>纹理数量</div>
                </div>
              </div>

              <div style={sectionStyle}>
                <h3 style={sectionTitleStyle}>引用列表</h3>
                {result.analysis.references.map((ref, refIndex) => (
                  <div key={`${ref.path}-${refIndex}`} style={itemStyle}>
                    <p style={itemPathStyle}>{ref.path}</p>
                    <p style={itemDetailStyle}>类型: {ref.type}</p>
                    {ref.prim_path && (
                      <p style={itemDetailStyle}>Prim路径: {ref.prim_path}</p>
                    )}
                  </div>
                ))}
              </div>

              {result.analysis.textures.length > 0 && (
                <div style={sectionStyle}>
                  <h3 style={sectionTitleStyle}>纹理列表</h3>
                  {result.analysis.textures.map((texture, texIndex) => (
                    <div key={`${texture.path}-${texIndex}`} style={itemStyle}>
                      <p style={itemPathStyle}>{texture.path}</p>
                      <p style={itemDetailStyle}>Shader: {texture.shader}</p>
                      <p style={itemDetailStyle}>输入: {texture.input}</p>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div style={errorStyle}>
              <p>{result.analysis.error}</p>
            </div>
          )}
        </div>
      ))}

      <style jsx global>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        body {
          color: rgb(255, 255, 255);
          background: linear-gradient(
            to bottom,
            rgb(17, 24, 39),
            rgb(31, 41, 55)
          );
          min-height: 100vh;
          font-family: Arial, Helvetica, sans-serif;
          margin: 0;
          padding: 0;
        }
      `}</style>
    </main>
  )
}
