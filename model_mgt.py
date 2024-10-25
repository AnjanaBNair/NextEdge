import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, classification_report
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split  # Import the train_test_split function

# Load existing course and enrollment data
def load_data():
    try:
        courses_df = pd.read_csv('course_synthetic.csv')
        enrollments_df = pd.read_csv('enrollment_synthetic.csv')
        
        print("Courses DataFrame:", courses_df.head())
        print("Enrollments DataFrame:", enrollments_df.head())
        
        # Returning only the two DataFrames
        return courses_df, enrollments_df
    except Exception as e:
        print("Error loading data:", str(e))
        raise e 

# Prepare Data for Training
def prepare_data(enrollments_df):
    # Create a pivot table to have students as rows and courses as columns
    pivot_df = enrollments_df.pivot_table(index='student_id', columns='course_id', aggfunc='size', fill_value=0)
    X = pivot_df.values  # Features: Enrolled courses
    y = (X > 0).astype(int)  # Target: Recommended courses (1 for enrolled, 0 for not)
    print(f'Prepared data with shapes: X={X.shape}, y={y.shape}')  # Log data shapes
    return pivot_df, X, y

# Train the Model
def train_model(X_train, y_train, X_test, y_test):
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f'Model accuracy: {accuracy * 100:.2f}%')
    print(classification_report(y_test, y_pred))
    
    return model

# Save the Model
def save_model(model):
    joblib.dump(model, 'course_recommendation_model.pkl')
    print('Model saved as course_recommendation_model.pkl')  # Log model saving

# Add New Course and Retrain the Model
def add_new_course(course_info, new_enrollments, courses_df, enrollments_df):
    # Add new course
    new_course_df = pd.DataFrame([course_info], columns=courses_df.columns)
    courses_df = pd.concat([courses_df, new_course_df], ignore_index=True)
    courses_df.to_csv('course_synthetic.csv', index=False)  # Save updated course data

    # Update enrollment data with new enrollments
    for student_id in new_enrollments:
        enrollments_df = pd.concat([enrollments_df, pd.DataFrame({'student_id': [student_id], 'course_id': [course_info[0]]})], ignore_index=True)
    
    enrollments_df.to_csv('enrollment_synthetic.csv', index=False)  # Save updated enrollment data

    # Prepare and train the model again
    pivot_df, X, y = prepare_data(enrollments_df)
    model = train_model(X, y)
    save_model(model)

# Example usage to train the model initially (could be called on an admin page or similar)
def initial_training():
    courses_df, enrollments_df = load_data()
    pivot_df, X, y = prepare_data(enrollments_df)
    
    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)  # Use 20% for testing
    
    model = train_model(X_train, y_train, X_test, y_test)  # Pass the split data to train_model
    save_model(model)

if __name__ == "__main__":
    # Call the initial training function to train the model
    initial_training()
