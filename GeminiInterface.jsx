import React, { useState, useEffect } from 'react';
import { Sparkles, Upload, Video, Image, Send, Loader2 } from 'lucide-react';

// WaveAnimation 컴포넌트
const WaveAnimation = () => {
  return (
    <div className="absolute bottom-0 left-0 w-full h-32 overflow-hidden">
      <svg
        className="absolute bottom-0 w-full h-full"
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
      >
        <path
          d="M0,60 C300,20 600,100 1200,60 L1200,120 L0,120 Z"
          fill="url(#gradient)"
          className="animate-pulse"
        >
          <animateTransform
            attributeName="transform"
            attributeType="XML"
            type="translate"
            values="0 0;-50 0;0 0"
            dur="8s"
            repeatCount="indefinite"
          />
        </path>
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#4facfe" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#00f2fe" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#ff69b4" stopOpacity="0.4" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
};

// ResultView 컴포넌트
const ResultView = ({ result, isLoading }) => {
  if (isLoading) {
    return (
      <div className="mt-16 flex flex-col items-center space-y-4">
        <div className="relative">
          <div className="w-16 h-16 border-4 border-blue-400/30 border-t-blue-400 rounded-full animate-spin"></div>
          <div className="absolute inset-0 w-16 h-16 border-4 border-purple-400/20 border-r-purple-400 rounded-full animate-spin animation-delay-150"></div>
        </div>
        <p className="text-gray-300 text-lg">AI가 분석하고 있습니다...</p>
        <div className="flex space-x-1">
          <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce animation-delay-100"></div>
          <div className="w-2 h-2 bg-pink-400 rounded-full animate-bounce animation-delay-200"></div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="mt-16 max-w-4xl w-full">
      <div className="bg-white/5 backdrop-blur-md rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-semibold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
          ✨ 분석 결과
        </h3>
        
        {result.type === 'image' && (
          <div className="space-y-4">
            <div className="bg-white/10 rounded-2xl p-4">
              <Image className="w-8 h-8 text-blue-400 mb-2" />
              <h4 className="text-lg font-medium">이미지 분석</h4>
              <p className="text-gray-300">{result.description}</p>
            </div>
          </div>
        )}

        {result.type === 'video' && (
          <div className="space-y-4">
            <div className="bg-white/10 rounded-2xl p-4">
              <Video className="w-8 h-8 text-purple-400 mb-2" />
              <h4 className="text-lg font-medium">영상 생성</h4>
              <p className="text-gray-300">{result.description}</p>
            </div>
          </div>
        )}

        {result.type === 'text' && (
          <div className="space-y-4">
            <div className="bg-white/10 rounded-2xl p-4">
              <Sparkles className="w-8 h-8 text-yellow-400 mb-2" />
              <h4 className="text-lg font-medium">텍스트 분석</h4>
              <p className="text-gray-300">{result.description}</p>
            </div>
          </div>
        )}

        <div className="mt-6 p-4 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-2xl">
          <h5 className="font-medium mb-2">🎯 생성된 콘텐츠:</h5>
          <div className="space-y-2">
            {result.content?.map((item, index) => (
              <div key={index} className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-gradient-to-r from-blue-400 to-purple-500 rounded-full"></div>
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// 메인 GeminiInterface 컴포넌트
export default function GeminiInterface() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);

  // 파일 업로드 핸들러
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setUploadedFile(file);
      setInput(prev => prev + ` [업로드된 파일: ${file.name}]`);
    }
  };

  // 입력 처리 함수
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setIsLoading(true);
    setResult(null);

    // 시뮬레이션된 AI 응답 (실제로는 API 호출)
    setTimeout(() => {
      const mockResult = {
        type: input.includes('영상') || input.includes('비디오') ? 'video' : 
              uploadedFile?.type.startsWith('image/') ? 'image' : 'text',
        description: uploadedFile 
          ? `업로드된 ${uploadedFile.name} 파일을 분석했습니다.`
          : input.includes('영상') 
            ? '영상 생성 요청을 처리했습니다.'
            : '텍스트를 분석하고 관련 콘텐츠를 생성했습니다.',
        content: [
          '광고 스토리보드 생성',
          '미드저니 프롬프트 추천',
          '15초 리얼스 콘셉트',
          '타겟 오디언스 분석'
        ]
      };
      
      setResult(mockResult);
      setIsLoading(false);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-gray-900 to-black text-white flex flex-col items-center justify-center relative overflow-hidden">
      {/* 배경 그라데이션 오버레이 */}
      <div className="absolute inset-0 bg-gradient-to-r from-blue-900/20 via-purple-900/20 to-pink-900/20"></div>
      
      {/* Hero 섹션 */}
      <div className="relative z-10 text-center px-6">
        <h1 className="text-6xl md:text-8xl font-bold tracking-wide mb-4">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500">
            ✦ AI 광고 크리에이터 ✦
          </span>
        </h1>
        
        <div className="flex items-center justify-center space-x-2 mb-8">
          <Sparkles className="w-8 h-8 text-yellow-400 animate-pulse" />
          <p className="text-xl text-gray-300 font-light">
            당신의 아이디어를 현실로 만들어보세요
          </p>
          <Sparkles className="w-8 h-8 text-yellow-400 animate-pulse" />
        </div>

        {/* 중앙 입력 영역 */}
        <form onSubmit={handleSubmit} className="max-w-4xl w-full mx-auto">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="무엇이든 입력해보세요... 예: '스마트워치 30초 광고 만들어줘'"
              className="w-full px-8 py-6 rounded-full bg-white/10 backdrop-blur-md text-white text-lg placeholder-gray-300 focus:outline-none focus:ring-4 focus:ring-blue-500/30 focus:bg-white/15 transition-all duration-300 border border-white/20"
              disabled={isLoading}
            />
            
            {/* 파일 업로드 버튼 */}
            <label className="absolute right-4 top-1/2 transform -translate-y-1/2 cursor-pointer">
              <Upload className="w-6 h-6 text-gray-400 hover:text-white transition-colors" />
              <input
                type="file"
                accept="image/*,video/*"
                onChange={handleFileUpload}
                className="hidden"
                disabled={isLoading}
              />
            </label>
          </div>

          {/* 전송 버튼 */}
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="mt-6 px-8 py-3 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 flex items-center space-x-2 mx-auto shadow-lg shadow-blue-500/25"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>생성 중...</span>
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                <span>생성하기</span>
              </>
            )}
          </button>
        </form>

        {/* 업로드된 파일 표시 */}
        {uploadedFile && (
          <div className="mt-4 p-3 bg-white/10 rounded-full backdrop-blur-md border border-white/20 inline-flex items-center space-x-2">
            <Image className="w-4 h-4 text-blue-400" />
            <span className="text-sm">{uploadedFile.name}</span>
            <button
              onClick={() => {
                setUploadedFile(null);
                setInput(input.replace(` [업로드된 파일: ${uploadedFile.name}]`, ''));
              }}
              className="text-gray-400 hover:text-white"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {/* 결과 표시 영역 */}
      <ResultView result={result} isLoading={isLoading} />

      {/* WaveAnimation */}
      <WaveAnimation />

      {/* Footer */}
      <footer className="absolute bottom-6 left-1/2 transform -translate-x-1/2 text-center">
        <p className="text-gray-400 text-sm">
          💡 <strong className="text-blue-400">팁:</strong> 구체적인 설명을 입력할수록 더 정확한 결과를 얻을 수 있습니다
        </p>
      </footer>

      {/* 커스텀 스타일 */}
      <style jsx>{`
        .animation-delay-100 {
          animation-delay: 0.1s;
        }
        .animation-delay-150 {
          animation-delay: 0.15s;
        }
        .animation-delay-200 {
          animation-delay: 0.2s;
        }
      `}</style>
    </div>
  );
}
