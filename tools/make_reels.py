import argparse, sys, time
from services.reels_pipeline import generate_reels

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="제품 이미지 경로 (png 권장)")
    ap.add_argument("--template", default="configs/shot_templates/reels_city_studio.json")
    ap.add_argument("--out", default="outputs/videos/reels_out.mp4")
    ap.add_argument("--no-svd", action="store_true", help="SVD 끄기(완전 안전모드)")
    args = ap.parse_args()

    print(f"이미지: {args.image}")
    print(f"템플릿: {args.template}")
    print(f"출력: {args.out}")
    print("시작...")

    bar_len = 30
    def progress(p, msg):
        filled = int(bar_len * p / 100)
        bar = "#"*filled + "-"*(bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {p:3d}%  {msg:50s}")
        sys.stdout.flush()
        if p >= 100: print()

    try:
        generate_reels(
            product_path=args.image,
            template_path=args.template,
            out_path=args.out,
            use_svd=not args.no_svd,
            progress=progress
        )
        print("완료!")
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()