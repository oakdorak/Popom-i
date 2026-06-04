// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "BetoVision",
    platforms: [
        .iOS(.v15)
    ],
    products: [
        .library(name: "BetoVision", targets: ["BetoVision"])
    ],
    dependencies: [],
    targets: [
        .target(name: "BetoVision", dependencies: []),
        .testTarget(name: "BetoVisionTests", dependencies: ["BetoVision"])
    ]
)
