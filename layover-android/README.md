# Layover Logbook for Android (Google Play)

This Android app opens the Layover Logbook website (`https://karawene112.github.io/layover/app.html`) full screen through Chrome, with no browser bar. This kind of app is called a Trusted Web Activity. When you update the website, the app updates too, so you only upload a new app version when this project changes.

- Package name: `com.karawene.layoverlogbook`
- Target API: 36 (required for new apps on Google Play from 31 August 2026)

## 1. Build the app in Android Studio

1. Open Android Studio, choose **File → Open** and select this `layover-android` folder.
2. Wait for **Gradle sync** to finish. If Android Studio offers to upgrade the Android Gradle Plugin or Gradle, accept.
3. Try it on a phone or emulator: press **Run ▶**. The browser bar stays visible until step 3 below is done. That's normal.
4. Make the file for Google Play: **Build → Generate Signed App Bundle or APK → Android App Bundle → Create new…** key store.
   - Save the `.jks` file and its passwords somewhere safe, outside this project. If you lose them, you can't update the app.
   - Choose **release**. The file is saved at `app/release/app-release.aab`.

## 2. Create the app in Google Play Console

1. At play.google.com/console, pay the one-time $25 developer fee, then **Create app**.
2. Name the app "Layover Logbook", set it as an **App**, and make it **Free**.
3. Fill in the store listing, privacy policy (`https://karawene112.github.io/layover/privacy-policy.html`), content rating, data safety and target audience.
4. Under **Testing → Closed testing**, create a track and upload `app-release.aab`.
5. A new personal developer account needs **at least 12 testers opted in for 14 days in a row** before it can apply for production. Add 15 to 20 crew Gmail addresses so you stay above 12 if a few drop out.

## 3. Link the app and the website (removes the browser bar)

1. In Play Console, go to **Test and release → App integrity → App signing** and copy the **SHA-256 certificate fingerprint** of the *app signing key*.
2. Put it in `/.well-known/assetlinks.json` at the root of the website repository, in place of `REPLACE_WITH_APP_SIGNING_KEY_SHA256_FROM_PLAY_CONSOLE`.
   To test your own build before uploading, add the fingerprint of your upload key (shown in the same place) as a second line.
3. Push. Check that `https://karawene112.github.io/.well-known/assetlinks.json` opens.

## Payments in the Android app

Google Play requires its own billing for digital subscriptions bought inside an app. So when the website runs inside this app (it opens with `?src=android`), the Pro screen hides the Paddle plans and says that people who already have Pro can sign in to unlock it. Pro bought on the website works in the app after signing in. Selling Pro inside the app would need Google Play Billing, which is a separate project.

## Updating the app

Add 1 to `versionCode` in `app/build.gradle`, build a new signed bundle (step 1.4) and upload it in Play Console.
